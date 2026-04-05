import { createTheme } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'indigo',
  defaultRadius: 'md',
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
  headings: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
    fontWeight: '700',
  },
  colors: {
    dark: [
      '#C9C9C9', '#b8b8b8', '#828282', '#696969',
      '#424242', '#3b3b3b', '#2e2e2e', '#242424',
      '#1f1f1f', '#141414',
    ],
  },
  other: {
    positiveColor: '#12b886',
    negativeColor: '#fa5252',
  },
});
