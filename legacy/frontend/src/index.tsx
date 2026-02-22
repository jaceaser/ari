import React, { useState, useEffect } from 'react';
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route, RouterProvider } from "react-router-dom";
import { initializeIcons } from "@fluentui/react";
import "./index.css";


import Home from "./pages/home/Home";
import ChatLayout from "./pages/layout/ChatLayout";
import Layout from "./pages/layout/Layout";
import Chat from "./pages/chat/Chat";
import NoPage from "./pages/NoPage";
import Profile from "./pages/profile/Profile";
import { AppStateProvider } from "./state/AppProvider";
import { Auth0Provider } from '@auth0/auth0-react';
import ProtectedRoute from "./components/auth0/ProtectedRoute"
import SplashScreen from './components/SplashScreen/SplashScreen';

initializeIcons();

// const domain = process.env.REACT_APP_AUTH0_DOMAIN as string;
// const clientId = process.env.REACT_APP_AUTH0_CLIENT_ID as string;

const domain = "dev-xuisgwrnqlxuxdgp.us.auth0.com";
const clientId = "VUOl4ndAQAyOViD2lbiN2iNqJXqnh5KU";
const redirect_url = window.location.origin + "/#/landing"

export default function App() {
    return (
        // <Auth0Provider domain={domain} clientId={clientId} authorizationParams={{ redirect_uri: redirect_url }}>
            <AppStateProvider>
                <HashRouter>
                    <Routes>
                        <Route path="/" element={<ChatLayout />}>
                            <Route index element={<Chat />} />
                            <Route path="*" element={<NoPage />} />
                        </Route>
                        <Route path="/chat" element={<ChatLayout />}>
                            <Route index element={<Chat />} />
                            <Route path="*" element={<NoPage />} />
                        </Route>
                        <Route path="/profile" element={<Layout />}>
                            <Route index element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                            <Route path="*" element={<NoPage />} />
                        </Route>
                        <Route path="/landing" element={<Layout />}>
                            <Route index element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                            <Route path="*" element={<NoPage />} />
                        </Route>
                    </Routes>
                </HashRouter>
            </AppStateProvider>
        // </Auth0Provider>
    );
}

// ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
//     <React.StrictMode>
//         <App />
//     </React.StrictMode>
// );


const Root = () => {
  const [showSplash, setShowSplash] = useState(true);

  useEffect(() => {
    const timeout = setTimeout(() => setShowSplash(false), 3000); // 3s splash
    return () => clearTimeout(timeout);
  }, []);

  return showSplash ? <SplashScreen /> : <App />;
};

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
