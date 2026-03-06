/**
 * ARI design tokens — mirrors apps/web/app/globals.css
 * Primary brand: gold hsl(41 92% 67%) = #F7C35D
 */
export const colors = {
  // Brand
  primary:            '#F7C35D', // hsl(41 92% 67%) — ARI gold
  primaryForeground:  '#1A1A27', // hsl(240 10% 10%)

  // Backgrounds
  background:         '#FFFFFF',
  card:               '#FFFFFF',
  sidebarBg:          '#FAFAFA', // hsl(0 0% 98%)

  // Text
  foreground:         '#09090F', // hsl(240 10% 3.9%)
  mutedForeground:    '#737382', // hsl(240 3.8% 46.1%)

  // Surfaces
  muted:              '#F4F4F6', // hsl(240 4.8% 95.9%)
  secondary:          '#F4F4F6',

  // Borders
  border:             '#E4E4EA', // hsl(240 5.9% 90%)
  input:              '#E4E4EA',

  // States
  destructive:        '#EF4444', // hsl(0 84.2% 60.2%)
  ring:               '#F7C35D',

  // User bubble (keep contrast on gold background)
  userBubble:         '#F7C35D',
  userBubbleText:     '#1A1A27',
  assistantBubble:    '#F4F4F6',
  assistantBubbleText:'#09090F',
} as const;
