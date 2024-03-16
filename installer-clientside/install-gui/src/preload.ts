import { contextBridge, ipcRenderer } from 'electron';
import { InstallerProps, InstallerParams } from './renderer.d';

const printers: { [key: string]: string } = {};

contextBridge.exposeInMainWorld('electronAPI', {
  log: (...args: any[]) => { ipcRenderer.send('log', ...args); },
  subscribeInstallerProps: () => ipcRenderer.send('subscribeInstallerProps'),
  connectPrinter: (ip: string, serial: string, accessCode: string, sshPassword?: string) => ipcRenderer.send('connectPrinter', ip, serial, accessCode, sshPassword),
  startInstall: () => ipcRenderer.send('startInstall'),
  startRecovery: () => ipcRenderer.send('startRecovery'),
  getStore: (key: string) => ipcRenderer.sendSync('getStore', key),
  setParams: (params: InstallerParams) => ipcRenderer.send('setParams', params),
});

ipcRenderer.on('newInstallerProps', (ev, props: InstallerProps) => {
  window.dispatchEvent(new CustomEvent('new-installer-props', {detail: props}));
});