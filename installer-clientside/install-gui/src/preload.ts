import { contextBridge, ipcRenderer } from 'electron';
import { InstallerProps, InstallerParams } from './renderer.d';

const printers: { [key: string]: string } = {};

contextBridge.exposeInMainWorld('electronAPI', {
  log: (...args: any[]) => { ipcRenderer.send('log', ...args); },
  subscribeInstallerProps: () => ipcRenderer.send('subscribeInstallerProps'),
  connectPrinter: (ip: string, accessCode: string, serial?: string, sshPassword?: string) => ipcRenderer.send('connectPrinter', ip, accessCode, serial, sshPassword),
  startInstall: () => ipcRenderer.send('startInstall'),
  startRecovery: () => ipcRenderer.send('startRecovery'),
  getStore: (key: string) => ipcRenderer.sendSync('getStore', key),
  setParams: (params: InstallerParams) => ipcRenderer.send('setParams', params),
  querySerial: (ip: string, accessCode: string) => ipcRenderer.invoke('querySerial', ip, accessCode),
});

ipcRenderer.on('newInstallerProps', (ev, props: InstallerProps) => {
  window.dispatchEvent(new CustomEvent('new-installer-props', {detail: props}));
});