import { useEffect, useRef, useState } from 'react';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

export type NetworkStatus = {
  isConnected: boolean;
  /** true only after we've confirmed network state at least once */
  ready: boolean;
};

export function useNetworkStatus(): NetworkStatus {
  const [state, setState] = useState<NetworkStatus>({ isConnected: true, ready: false });
  const readyRef = useRef(false);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((info: NetInfoState) => {
      const connected = info.isConnected !== false && info.isInternetReachable !== false;
      readyRef.current = true;
      setState({ isConnected: connected, ready: true });
    });

    // Kick off an immediate fetch
    NetInfo.fetch().then((info: NetInfoState) => {
      if (!readyRef.current) {
        const connected = info.isConnected !== false && info.isInternetReachable !== false;
        setState({ isConnected: connected, ready: true });
      }
    });

    return unsubscribe;
  }, []);

  return state;
}
