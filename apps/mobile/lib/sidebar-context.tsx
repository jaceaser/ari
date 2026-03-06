import React, { createContext, useContext, useRef, useState } from 'react';
import { Animated } from 'react-native';

export const SIDEBAR_WIDTH = 300;

type SidebarContextType = {
  isOpen: boolean;
  anim: Animated.Value;
  open: () => void;
  close: () => void;
};

const SidebarContext = createContext<SidebarContextType>({
  isOpen: false,
  anim: new Animated.Value(0),
  open: () => {},
  close: () => {},
});

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const anim = useRef(new Animated.Value(0)).current;

  const open = () => {
    setIsOpen(true);
    Animated.spring(anim, {
      toValue: 1,
      useNativeDriver: true,
      tension: 68,
      friction: 12,
    }).start();
  };

  const close = () => {
    Animated.timing(anim, {
      toValue: 0,
      duration: 220,
      useNativeDriver: true,
    }).start(() => setIsOpen(false));
  };

  return (
    <SidebarContext.Provider value={{ isOpen, anim, open, close }}>
      {children}
    </SidebarContext.Provider>
  );
}

export const useSidebar = () => useContext(SidebarContext);
