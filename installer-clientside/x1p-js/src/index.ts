import { program } from 'commander';
import ftp from 'basic-ftp';
import mqtt from 'async-mqtt';
import { NodeSSH } from 'node-ssh';
import ssdp from 'node-ssdp';
import stream from 'stream';
import { Printer, findPrinter } from './x1p.js';

program.option('-i, --ip <ipaddr>', 'IP address of printer');
program.requiredOption('-a, --access_code <access-code>', 'LAN access code');
program.parse();
const opts = program.opts();

async function doit() {
    console.log("looking for printer with SSDP...")
    const {host, serial} = await findPrinter(opts.ip);
    if (opts.ip === undefined) {
        opts.ip = host;
    }
    console.log(`found printer serial number ${serial} ip ${host}`);

    const printer = new Printer(opts.ip, opts.access_code);
    console.log("authenticating to printer...");
    await printer.authenticate();
}

await doit();
