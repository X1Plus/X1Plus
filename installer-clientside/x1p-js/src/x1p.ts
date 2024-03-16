import {Client as FTPClient} from 'basic-ftp';
import mqtt from 'async-mqtt';
import { NodeSSH } from 'node-ssh';
import EventEmitter from 'node:events';
import dgram from 'dgram';

/* We really want to listen on multicast 255.255.255.255:2021, since the
 * printer does not always answer on 239.255.255.250; node-ssdp doesn't do
 * that, so we hand-code this implementation here.
 */
const SSDP_PORT = 2021;
var ssdpEvent = new EventEmitter();
var ssdpSock = dgram.createSocket({type: 'udp4', reuseAddr: true});
ssdpSock.bind(SSDP_PORT, '0.0.0.0');
ssdpSock.on('listening', function () {
    ssdpSock.setBroadcast(true);
    ssdpSock.send(Buffer.from('M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1990\r\nST: urn:bambulab-com:device:3dprinter:1\r\nMAN: "ssdp:discover"\r\nMX: 3\r\n\r\n'), SSDP_PORT, '255.255.255.255');
});
var printersSeen = [];
ssdpSock.on('message', function (m: Buffer, r: any) {
    const ip = r.address;
    const headers = m.toString().split('\r\n\r\n')[0].split('\r\n');
    const method = headers.shift();
    if (method != 'NOTIFY * HTTP/1.1' && method != 'HTTP/1.1 200 OK' && method != 'M-SEARCH * HTTP/1.1') {
        console.log(`x1p.ts: weird SSDP message ${method} (${m.toString()}), ignoring`);
        return;
    }
    var hdrmap = { };
    for (const hdr of headers.values()) {
        const kv = hdr.split(': ');
        hdrmap[kv[0]] = kv[1];
    }
    if ((hdrmap['DevModel.bambu.com'] == 'BL-P001' || hdrmap['DevModel.bambu.com'] == 'BL-P002') && (hdrmap['NT'] == 'urn:bambulab-com:device:3dprinter:1' || hdrmap['ST'] == 'urn:bambulab-com:device:3dprinter:1') && hdrmap['Location'] && hdrmap['USN']) {
        if (!printersSeen.includes(hdrmap['USN'])) {
            console.log(`x1p.ts: discovered printer ${hdrmap['Location']} (${hdrmap['USN']}) with method ${method}`);
            printersSeen.push(hdrmap['USN']);
        }
        ssdpEvent.emit('discovered', hdrmap['Location'], hdrmap['USN']);
    }
});

export function findPrinters(cbk: (ip: string, sn: string) => void) {
    ssdpEvent.on('discovered', cbk);
}

export function findPrinter(host?: string): Promise<Printer> {
    return new Promise<Printer>((resolve) => {
        const waiting_thread = setInterval(() => {}, 100); /* this is janky and I don't understand how to do this impedance match otherwise */
        findPrinters((ip, sn) => {
            if (host === undefined || ip == host) {
                clearInterval(waiting_thread);
                resolve(new Printer(ip));
            }
        });
    });
}

export class Printer {
    host: string;
    serial?: string;
    accessCode?: string;
    printStatus?: object;

    ftpsUser = "bblp";
    ftpsPort = 990;
    ftpsTimeout = 5000;

    mqttUser = "bblp";

    sshPass: string;
    sshUser: string;
    sshPort: number;
    
    ftpClient?: FTPClient;
    mqttClient?: mqtt.AsyncMqttClient;
    sshClient?: NodeSSH;

    constructor(host: string) {
        this.host = host;
        this.sshUser = "x1plus";
        this.sshPort = 2222;
    }
    
    mqttRecvAsync<T>(fn: (topic: string, msg: object, resolve: (T) => void, reject: (any) => void) => void) {
      const _this = this;
      return new Promise<T>((resolve, reject) => {
        function msg(topic: string, message: Uint8Array) {
          fn(topic, JSON.parse(new TextDecoder().decode(message)),
              (x: T) => { _this.mqttClient.off('message', msg); resolve(x); },
              (x: any) => { _this.mqttClient.off('message', msg); reject(x); });
        }
        _this.mqttClient.on('message', msg);
      });
    }
    
    async mqttSend(msg: object) {
      await this.mqttClient.publish(`device/${this.serial}/request`, JSON.stringify(msg));
    }
    
    async waitPrintStatus() {
      if (this.printStatus !== undefined) {
        return this.printStatus;
      }
      return await this.mqttRecvAsync((topic, msg, resolve) => {
        if ('print' in msg && ((msg['print']['msg'] === undefined) || (msg['print']['msg'] === 0))) {
          resolve(msg.print);
        }
      });
    }
    
    async authenticate(accessCode?: string) {
        if (accessCode !== undefined) {
            this.accessCode = accessCode;
        }
        
        if (this.accessCode === undefined) {
            throw new Error("call to authenticate() without an accessCode");
        }
        
        try {
            await this.disconnect();

            console.log("x1p.ts::Printer: connecting to MQTT broker...");
            try {
                this.mqttClient = await mqtt.connectAsync(`mqtts://${this.host}/`, { 'username': 'bblp', 'password': this.accessCode, 'rejectUnauthorized': false});
            } catch(e) {
                try {
                    console.log(`x1p.ts::Printer: ${e}, maybe falling back on insecure MQTT?`);
                    this.mqttClient = await mqtt.connectAsync(`mqtt://${this.host}/`, { 'username': 'bblp', 'password': this.accessCode, 'rejectUnauthorized': false});
                } catch (e2) {
                    throw e;
                }
            }
            await this.mqttClient.subscribe(`device/+/report`);
            const _this = this;
            this.mqttRecvAsync((topic, msg) => {
              if ('print' in msg) {
                if ((msg['print']['msg'] === 1) || (msg['print']['msg'] === undefined)) {
                  _this.printStatus = msg.print as object;
                } else if (_this.printStatus !== undefined) {
                  Object.assign(_this.printStatus, msg.print);
                }
              }
            });
            
            console.log("x1p.ts::Printer: waiting for serial number message...");
            this.serial = await this.mqttRecvAsync((topic, msg, resolve) => resolve(topic.split('/')[1]));
            console.log(`x1p.ts::Printer: we appear to be serial number ${this.serial}`);
            
            console.log("x1p.ts::Printer: sending initial pushall request");
            this.mqttSend({ pushing: { sequence_id: "0", command: "pushall" } });

            console.log("x1p.ts::Printer: connecting to FTP server...");
            try {
                const ftpClient = new FTPClient(this.ftpsTimeout);
                await ftpClient.access({host: this.host, port: this.ftpsPort, user: this.ftpsUser, password: this.accessCode, secure: 'implicit', secureOptions: {rejectUnauthorized: false, secureProtocol: 'TLSv1_2_method'}});
                this.ftpClient = ftpClient;
            } catch (e) {
                try {
                    console.log(`x1p.ts::Printer: ${e}, maybe falling back on insecure FTP?`);
                    const ftpClient = new FTPClient(this.ftpsTimeout);
                    await ftpClient.access({host: this.host, user: this.ftpsUser, password: this.accessCode,});
                    this.ftpClient = ftpClient;
                } catch (e2) {
                    throw e;
                }
            }
            console.log("x1p.ts::Printer: authenticated");
        } catch (e) {
            await this.disconnect();
            throw e;
        }
    }
    
    async disconnect() {
        if (this.mqttClient) {
            this.mqttClient.end();
            this.mqttClient = null;
        }
        
        if (this.ftpClient) {
            this.ftpClient.close();
            this.ftpClient = null;
        }
        
        if (this.sshClient) {
            this.sshClient.dispose();
            this.sshClient = null;
        }
    }

    async connectSSH() {
        const ssh = new NodeSSH();
        this.sshClient = await ssh.connect({
            host: this.host,
            port: this.sshPort,
            username: this.sshUser,
            password: this.sshPass
        });
    }
}
