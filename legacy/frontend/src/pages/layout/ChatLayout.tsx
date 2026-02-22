import { Navigate, Outlet, Link } from "react-router-dom";
import styles from "./ChatLayout.module.css";
import uc from "../../assets/UC-logo-3.png";
import { Stack } from "@fluentui/react";
import { useContext, useEffect } from "react";
import { HistoryButton } from "../../components/common/Button";
import { LogoutButton } from "../../components/common/Button";
import { AppStateContext } from "../../state/AppProvider";
import { CosmosDBStatus } from "../../api";
import { useAuth0 } from "@auth0/auth0-react";

const ChatLayout = () => {
    const appStateContext = useContext(AppStateContext)
    const { logout, isAuthenticated } = useAuth0();

    const handleHistoryClick = () => {
        appStateContext?.dispatch({ type: 'TOGGLE_CHAT_HISTORY' })
    };

    const handleLogoutClick = () => {
        logout({ logoutParams: { returnTo: window.location.origin } });
      };

    useEffect(() => { }, [appStateContext?.state.isCosmosDBAvailable.status]);

    return (
        <div className={styles.layout}>
            {/* <header className={styles.header} role={"banner"}>
                <Stack horizontal verticalAlign="center" horizontalAlign="space-between">
                    <Stack horizontal verticalAlign="center">
                        <img
                            src={uc}
                            className={styles.headerIcon}
                            aria-hidden="true"
                        />
                        <Link to="/" className={styles.headerTitleContainer}>
                            <h1 className={styles.headerTitle}>ARI</h1>
                        </Link>
                    </Stack>
                    <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 4 }}>
                        { {(appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured) &&
                            <HistoryButton onClick={handleHistoryClick} text={appStateContext?.state?.isChatHistoryOpen ? "Hide chat history" : "Show chat history"} />
                        } }
                        <LogoutButton onClick={handleLogoutClick} text={"Logout"} />
                    </Stack>

                </Stack>
            </header> */}
            <Outlet />
        </div>
    );
};

export default ChatLayout;
