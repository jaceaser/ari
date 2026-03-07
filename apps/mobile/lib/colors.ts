/**
 * ARI design tokens — mirrors apps/web/app/globals.css
 * Primary brand: gold hsl(41 92% 67%) = #F7C35D
 */

const base = {
  primary:           '#F7C35D', // ARI gold — same in both modes
  primaryForeground: '#1A1A1A',
  destructive:       '#EF4444',
  ring:              '#F7C35D',
} as const;

export const lightColors = {
  ...base,
  background:         '#FFFFFF',
  card:               '#FFFFFF',
  sidebarBg:          '#FAFAFA',
  foreground:         '#09090F',
  mutedForeground:    '#737382',
  muted:              '#F4F4F6',
  secondary:          '#F4F4F6',
  border:             '#E4E4EA',
  input:              '#E4E4EA',
  userBubble:         '#F7C35D',
  userBubbleText:     '#1A1A1A',
  assistantBubble:    '#F4F4F6',
  assistantBubbleText:'#09090F',
} as const;

// Dark mode — matches apps/web/app/globals.css .dark tokens
export const darkColors = {
  ...base,
  background:         '#0D0D0D',
  card:               '#161616',
  sidebarBg:          '#0A0A0A',
  foreground:         '#FAFAFA',
  mutedForeground:    '#8C8C8C',
  muted:              '#1F1F1F',
  secondary:          '#1F1F1F',
  border:             '#262626',
  input:              '#262626',
  userBubble:         '#F7C35D',
  userBubbleText:     '#1A1A1A',
  assistantBubble:    '#1F1F1F',
  assistantBubbleText:'#FAFAFA',
} as const;

export type ColorTokens = typeof lightColors;

// Static light export kept so non-hook usages (StyleSheet outside components) still compile.
export const colors = lightColors;
