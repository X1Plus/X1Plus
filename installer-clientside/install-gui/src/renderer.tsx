import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { MantineProvider, createTheme, rem } from '@mantine/core';
import type { MantineColorsTuple } from '@mantine/core';
// core styles are required for all packages
import '@mantine/core/styles.css'; //eslint-disable-line import/no-unresolved
import './fonts.css';

// other css files are required only if
// you are using components from the corresponding package
// import '@mantine/dates/styles.css';
// import '@mantine/dropzone/styles.css';
// import '@mantine/code-highlight/styles.css';
// ...

const bambuColor: MantineColorsTuple = [ '#ebfff2', '#d5fee4', '#a5fdc5', '#72fda4', '#4ffd89', '#3dfd77', '#35fe6d', '#2ae25c', '#1ec850', '#00ad42'];

const theme = createTheme({
  fontFamily: 'HarmonyOS Sans SC',
  fontSizes: { xs: rem(12), sm: rem(14), md: rem(16), lg: rem(18), xl: rem(22), },
  colors: { bambuColor,  },
  primaryColor: 'bambuColor',
  black: '#545654',
  components: { Title: { defaultProps: { c: 'bambuColor.9' }, }, },
  /** Put your mantine theme override here */
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <MantineProvider theme={theme} forceColorScheme="dark">
      <App />
    </MantineProvider>
  </React.StrictMode>
);
