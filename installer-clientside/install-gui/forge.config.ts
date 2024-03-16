import type { ForgeConfig } from '@electron-forge/shared-types';
import { MakerSquirrel } from '@electron-forge/maker-squirrel';
import { MakerZIP } from '@electron-forge/maker-zip';
import { MakerDeb } from '@electron-forge/maker-deb';
import { MakerRpm } from '@electron-forge/maker-rpm';
import { MakerDMG } from '@electron-forge/maker-dmg';
import { AutoUnpackNativesPlugin } from '@electron-forge/plugin-auto-unpack-natives';
import { WebpackPlugin } from '@electron-forge/plugin-webpack';

import { mainConfig } from './webpack.main.config';
import { rendererConfig } from './webpack.renderer.config';

import fs from 'fs/promises';

const signingOpts = process.env.X1PLUS_CODESIGN ?
  {
    osxSign: {
      identity: 'Developer ID Application: Joshua Wise (54GTJ2AU36)',
    },
    osxNotarize: {
      appleApiKey: '/Users/joshua/work/x1plus/AuthKey_34CSB7LGJA.p8', // some day when we build Electron in CI this will have to come as a secret, but for now, here we are
      appleApiKeyId: '34CSB7LGJA',
      appleApiIssuer: '69a6de83-020f-47e3-e053-5b8c7c11a4d1',
    },
  } : {};

const config: ForgeConfig = {
  packagerConfig: {
    asar: true,
    icon: './src/img/icon',
    ...signingOpts
  },
  rebuildConfig: {},
  makers: [
    new MakerZIP({}, ['win32']),
    new MakerDMG({
      format: 'ULFO',
      icon: './src/img/icon.icns',
      background: './white-background.png',
      contents: opts => [
        {
          x: 128,
          y: 128,
          type: 'file',
          path: (opts as any).appPath,
        },
      ],
      iconSize: 256,
      additionalDMGOptions: {
        window: {
          size: {
            height: 370,
            width: 320,
          }
        }
      },
    })
  ],
  hooks: {
    packageAfterCopy: async (config, buildPath) => {
      // the extraResource path does not properly handle the symlink, so we do it ourselves, thx electron-forge
      await fs.copyFile(`${__dirname}/src/cfw.x1p`, `${buildPath}/../cfw.x1p`);
      await fs.copyFile(`${__dirname}/src/setup.tgz`, `${buildPath}/../setup.tgz`);
      await fs.copyFile(`${__dirname}/src/icon.png`, `${buildPath}/../icon.png`);
    }
  },
  plugins: [
    new AutoUnpackNativesPlugin({}),
    new WebpackPlugin({
      mainConfig,
      renderer: {
        config: rendererConfig,
        entryPoints: [
          {
            html: './src/index.html',
            js: './src/renderer.tsx',
            name: 'main_window',
            preload: {
              js: './src/preload.ts',
            },
          },
        ],
      },
    }),
  ],
};

export default config;
