import { Navigate, Outlet, Link } from "react-router-dom";
import styles from "./Layout.module.css";
import hbhs from "../../assets/HBHS-Gold-Logo-Flat.png";
import { Stack } from "@fluentui/react";
import { useContext, useEffect } from "react";
import { LogoutButton } from "../../components/common/Button";
import { AppStateContext } from "../../state/AppProvider";
import { useAuth0 } from "@auth0/auth0-react";

const Layout = () => {
    const appStateContext = useContext(AppStateContext)
    const { logout, isAuthenticated } = useAuth0();

    const handleLogoutClick = () => {
      logout({ logoutParams: { returnTo: window.location.origin } });
    };

    return (
        <div className={styles.layout}>
            <header className={styles.header} role={"banner"}>
                <Stack horizontal verticalAlign="center" horizontalAlign="space-between">
                    <Stack horizontal verticalAlign="center">
                        <img
                            src={hbhs}
                            className={styles.headerIcon}
                            aria-hidden="true"
                        />
                        <Link to="/" className={styles.headerTitleContainer}>
                            <h1 className={styles.headerTitle}>ARI</h1>
                        </Link>
                    </Stack>
                    <Stack horizontal tokens={{ childrenGap: 4 }}>
                      {/* <div className={styles.spacer}>
                        <LogoutButton onClick={handleLogoutClick} text={"Logout"} />
                      </div> */}
                    </Stack>

                </Stack>
            </header>
            <Outlet />
        </div>
    );
};

export default Layout;
