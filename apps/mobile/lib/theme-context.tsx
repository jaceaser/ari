import React, { createContext, useContext } from 'react';
import { useColorScheme } from 'react-native';
import { lightColors, darkColors, ColorTokens } from './colors';

const ThemeContext = createContext<ColorTokens>(lightColors);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const scheme = useColorScheme();
  const colors = scheme === 'dark' ? darkColors : lightColors;
  return <ThemeContext.Provider value={colors}>{children}</ThemeContext.Provider>;
}

/** Use inside any component to get the current theme's color tokens. */
export function useColors(): ColorTokens {
  return useContext(ThemeContext);
}
