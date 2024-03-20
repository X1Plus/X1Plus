import { AppShell, Checkbox, Image, Button, Box, Title, Text, Timeline, Center, Paper, Group, Stepper, Grid, Select, TextInput, Loader } from '@mantine/core';
import { useState, useEffect } from 'react';
import type { InstallerProps } from './renderer.d';

var x1plus_logo  = require('./img/x1plus.png').default;

window.electronAPI.log("App.js: startup");
console.log = window.electronAPI.log;

function InstallerGui(props: InstallerProps) {
  const [riskyOk, setRiskyOk] = useState(false);
  const [printerIp, setPrinterIp] = useState(null);
  const [printerAccessCode, setPrinterAccessCode] = useState(null);
  const [printerSshPassword, setPrinterSshPassword] = useState(null);
  const [installRightClicks, setInstallRightClicks] = useState(0);
  const [isManualIp, setIsManualIp] = useState(false);
  
  function serialForIp(ip: string): string|null {
    return props.printersAvailable.find(p => p.ip == ip)?.serial || null;
  }
  if (serialForIp(printerIp) && isManualIp) {
    /* if we have a serial, it is definitely in the list at this point */
    setIsManualIp(false);
  }

  async function updatePrinter(val: string) {
    if (val == printerIp)
      return;
    setPrinterIp(val);
    if (props.isConnected || !val) {
      setPrinterAccessCode(null);
      console.log(`InstallerGui: disconnecting`);
      window.electronAPI.connectPrinter(null, null, null);
    } else {
      const serial = serialForIp(val);
      let cachedAccessCode;
      let cachedSshPassword;
      if (serial) {
        cachedAccessCode = window.electronAPI.getStore(`printers.${serial}.accessCode`);
        cachedSshPassword = window.electronAPI.getStore(`printers.${serial}.sshPassword`);
      }
      
      const accessCode = cachedAccessCode || printerAccessCode;
      if (cachedAccessCode) {
        console.log(`InstallerGui: trying stored access code`);
        setPrinterAccessCode(cachedAccessCode);
      }
      const sshPassword = cachedSshPassword || printerSshPassword;
      if (cachedSshPassword) {
      	console.log(`InstallerGui: trying stored ssh password`);
      	setPrinterSshPassword(cachedSshPassword);
      }
      if (accessCode && accessCode.length == 8) {
        console.log(`InstallerGui: connecting because printer changed: ${val}`);
        window.electronAPI.connectPrinter(val, accessCode, serial, sshPassword);
      }
    }
  }
  
  async function updateAccessCode(val: string) {
    setPrinterAccessCode(val);
    if (val.length == 8) {
      console.log(`InstallerGui: connecting because printer access code changed: ${val}`);
      window.electronAPI.connectPrinter(printerIp, val, serialForIp(printerIp), printerSshPassword);
    }
  }
  
  async function updateSshPassword(val: string) {
    setPrinterSshPassword(val);
    if (val.length == 8) {
      console.log(`InstallerGui: connecting because printer ssh password changed: ${val}`);
      window.electronAPI.connectPrinter(printerIp, printerAccessCode, serialForIp(printerIp), val);
    }
  }

  return (
    <AppShell
      header={{ height: 80 }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md">
          <Title order={1}>
            X1Plus custom firmware installation
          </Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Stepper active={props.installFinished ? 2 : props.isInstalling ? 1 : 0} size="sm">
          <Stepper.Step label="Select printer">
            <Grid>
              <Grid.Col span={12}>
                Installing
                the X1Plus custom firmware on your printer will take about 10 to 15 minutes,
                depending on how fast your Internet connection is.  To get
                started, choose a printer to install X1Plus on.
              </Grid.Col>
              <Grid.Col span={6}>
                <p><b>Which printer?</b></p>
                <Select placeholder="Choose a printer"
                        value={isManualIp ? "$manual-input" : printerIp} onChange={(v) => {
                          if (v == "$manual-input") {
                            setIsManualIp(true);
                            setPrinterIp(null);
                            setPrinterAccessCode(null);
                            setPrinterSshPassword(null);
                          } else {
                            setIsManualIp(false);
                            updatePrinter(v);
                          }
                        }}
                        data={[
                          ...props.printersAvailable.map((p) => ({ value: p.ip, label: `${p.ip} (${p.serial})` }) ),
                          { value: "$manual-input", label: "Enter printer IP address manually..." }
                        ]}
                        disabled={props.isConnecting} />
                { isManualIp && <span>
                  <TextInput placeholder="aa.bb.cc.dd" value={printerIp} onChange={(ev) => updatePrinter(ev.currentTarget.value)} disabled={props.isConnecting}/>
                </span> }
              </Grid.Col>
              <Grid.Col span={6}>
                { printerIp != null && printerIp.trim().length > 0 &&
                  <>
                    <p><b>What's the LAN Access Code for this printer?</b></p>
                    <TextInput placeholder="abcd1234" value={printerAccessCode} onChange={(ev) => updateAccessCode(ev.currentTarget.value)} disabled={props.isConnecting || props.isConnected} />
                    { props.isConnected && <Text size="xs" c="green">Connected!</Text> }
                    { !props.isConnected && props.lastConnectionError && <Text size="xs" c="red">{props.lastConnectionError}</Text> }
                  </>
                }
              </Grid.Col>
              <Grid.Col span={6}>
                { props.isConnected && props.printerOtaVersion &&
                  <>
                    <Text><b>Current firmware version</b></Text>
                    <Text>{props.printerOtaVersion}</Text>
                    <Text size="xs" c={props.printerOtaVersionCompatible ? 'green' : 'red'}>
                      {props.printerOtaVersionMessage}
                    </Text>
                  </>
                }
              </Grid.Col>
              <Grid.Col span={6}>
                { props.isConnected && props.printerIsFirmwareR &&
                  <>
                    <Text><b>What's the root SSH password for this printer?</b></Text>
                    <TextInput placeholder="A1b2c3D4" value={printerSshPassword} onChange={(ev) => updateSshPassword(ev.currentTarget.value)} disabled={props.isConnecting || props.readyToInstall} />
                    { props.lastConnectionError == "" && <Text size="xs" c="green">Looks good!</Text> }
                    { props.lastConnectionError && <Text size="xs" c="red">{props.lastConnectionError}</Text> }
                  </>
                }
              </Grid.Col>
              { props.readyToInstall &&
                <Grid.Col span={12}>
                  <Checkbox color="red" checked={riskyOk} onChange={(ev) => setRiskyOk(ev.currentTarget.checked)} label="I know that installing custom firmware is risky, and I accept the risks." description="Although we've tried to make X1Plus as safe as possible for your printer, there are always inherent risks with installing third-party firmware on your printer. If X1Plus breaks your printer, you get to keep both pieces; X1Plus comes with NO WARRANTY, EXPRESS OR IMPLIED." />
                </Grid.Col>
              }
              { installRightClicks > 10 &&
                <Grid.Col span={12}>
                  <Checkbox color="red" onChange={(ev) => window.electronAPI.setParams({ wifiCompatibilityMode: ev.currentTarget.checked })}
                            label="Advanced: Enable WiFi compatibility mode" description="Check this if you are experiencing ECONNRESET problems while uploading the firmware to your printer.  If it helps, please let us know." />
                </Grid.Col>
              }
              <Grid.Col span={12}>
                <Button variant="filled" disabled={!props.readyToInstall || !riskyOk} onClick={window.electronAPI.startInstall} onContextMenu={() => setInstallRightClicks(installRightClicks + 1)}>Install X1Plus {props.bundledX1pVersion}!</Button>&nbsp;
                { installRightClicks > 10 && null &&
                  <Button variant="filled" disabled={!props.isConnected} onClick={window.electronAPI.startRecovery}>Recovery SSH console</Button>
                }
              </Grid.Col>
            </Grid>
          </Stepper.Step>
          <Stepper.Step label="Install">
            <Grid>
              <Grid.Col span={12}>
                {!props.installFailureMessage ?
                  <p><b>The X1Plus custom firmware is being transferred to your printer.  Do not turn your printer off.</b></p> :
                  <Text color="red.4"><b>X1Plus custom firmware installation has failed. Please report this error.</b></Text>}
              </Grid.Col>
              <Grid.Col span={12}>
                <Timeline active={props.currentStep-(props.installFailureMessage ? 0 : 1) || -1}>
                  {props.installSteps.map((k, i) => {
                      const isCurrent = i == props.currentStep;
                      if (props.installFailureMessage && isCurrent) {
                        return <Timeline.Item key={k} color="red.8" title={<div style={{paddingTop: '2px'}}><b>{k}</b></div>}>
                          <Text size="xs" color="red.4"><b>Installation has failed:</b> {props.installFailureMessage}</Text>
                        </Timeline.Item>;
                      }
                      if (isCurrent) {
                        return <Timeline.Item key={k} bullet={<Loader size={20} />} title={<div style={{paddingTop: '2px'}}><b>{k}</b></div>}>
                          {props.intraStatus && <Text size="xs">{props.intraStatus}</Text>}
                        </Timeline.Item>;
                      }
                      return <Timeline.Item key={k} title={<div style={{paddingTop: '2px'}}>{k}</div>} />;
                    }
                  )}
                </Timeline>
              </Grid.Col>
            </Grid>
          </Stepper.Step>
          <Stepper.Step label="Enjoy">
            <Center mih={600-170}>
              <Grid>
                <Grid.Col span={12}>
                  <Center><Image src={x1plus_logo} w={625}/></Center>
                </Grid.Col>
                <Grid.Col span={12}>
                  <Center><Text maw={450}>Congratulations!  The X1Plus
custom firmware has been successfully installed on your printer.  Reboot
your printer, and enjoy your new community-enhanced printer experience!
</Text></Center>
                </Grid.Col>
              </Grid>
            </Center>
          </Stepper.Step>
        </Stepper>
      </AppShell.Main>
    </AppShell>
  );
}

let globalProps : InstallerProps = {
  printersAvailable: [],
  isConnecting: false,
  isConnected: false,
  lastConnectionError: "",
  bundledX1pVersion: "",
  readyToInstall: false,
  isInstalling: false,
  installFinished: false,
  currentStep: 0,
  installSteps: [],
};

window.addEventListener('new-installer-props', (ev: any) => { globalProps = ev.detail; });
window.electronAPI.subscribeInstallerProps();

function App() {
  let [props, setProps] = useState(globalProps);

  useEffect(() => {
    function listener(ev: any) {
      setProps(ev.detail);
    }
    window.addEventListener('new-installer-props', listener);
    return () => window.removeEventListener('new-installer-props', listener);
  }, []);
  return <InstallerGui {...props} />;
}

export default App;
