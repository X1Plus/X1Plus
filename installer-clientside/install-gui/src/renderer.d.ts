export interface IElectronAPI {
  log: (...args: any[]) => void;
  subscribeInstallerProps: () => void;
  connectPrinter: (ip: string, serial: string, accessCode: string, sshPassword?: string) => Promise<void>;
  startInstall: () => void;
  startRecovery: () => void;
  getStore: (key: string) => any;
  setParams: (params: InstallerParams) => void;
}

declare global {
  interface Window {
    electronAPI: IElectronAPI
  }
}

export type PrinterAvailable = {
  ip: string;
  serial: string;
}

export type InstallerProps = {
  /* phase 1: selecting printer and verifying compatibility */
  printersAvailable: PrinterAvailable[];
  isConnecting: boolean; // should the access code / printer select GUI be greyed out
  isConnected: boolean;
  connectedPrinter?: PrinterAvailable;
  lastConnectionError: string;
  bundledX1pVersion: string;
  printerOtaVersion?: string;
  printerOtaVersionMessage?: string;
  printerOtaVersionCompatible?: boolean;
  printerIsFirmwareR?: boolean;
  printerCanHasFirmwareRUpgrade?: boolean;
  readyToInstall: boolean;
  
  /* phase 2: installing */
  isInstalling: boolean;
  currentStep: number;
  installSteps: string[];
  intraStatus?: string;
  installFailureMessage?: string;
  
  /* phase 3: finished */
  installFinished: boolean;
};

export type InstallerParams = {
  wifiCompatibilityMode: boolean;
};