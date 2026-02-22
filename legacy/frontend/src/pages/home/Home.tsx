import styles from "./Home.module.css";
import { Dialog, Stack, TextField, ICommandBarStyles, IButtonStyles } from "@fluentui/react";
import { LoginButton, SignUpButton } from "../../components/common/Button";
import { motion } from 'framer-motion';


// const HomePage = () => {
//     const { loginWithRedirect } = useAuth0();
//     const redirect_url = window.location.origin + "/#/landing"

//     const handleLoginClick = () => {
//         loginWithRedirect({authorizationParams:{ redirect_uri: redirect_url }});
//     };

//     const handleSignUpClick = () => {
//         loginWithRedirect({ authorizationParams: {
//         screen_hint: "signup",
//       }});
//     };

// PROD URL - "https://reilabs.ai/my-account/" DEV URL - http://localhost:50505/login

const HomePage = () => {
    const handleLoginClick = () => {
        window.location.href = "https://reilabs.ai/my-account/"; // or your deployed login URL 
    };

    const handleSignUpClick = () => {
        window.location.href = "https://reilabs.ai/my-account/"; // optional: a different URL if you handle signups differently
    };

    return (
        <div className={styles.layout}>
            <header className={styles.header} role={"banner"}>
                <Stack horizontal verticalAlign="center" horizontalAlign="space-between" className={styles.headerStack}>
                    <Stack horizontal verticalAlign="center">
                        <div className={styles.leftSpace} />
                        <div className={styles.ucLogo} />
                        <div className={styles.hbhslabs} >HBHS LABS</div>
                    </Stack>
                    <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 4 }} className={styles.loginStack}>
                        <LoginButton onClick={handleLoginClick} text={"Login"} />
                        <div className={styles.rightSpace} />
                    </Stack>
                </Stack>
            </header>
            <Stack  verticalAlign="center" horizontalAlign="center">
                <motion.h1
                    initial={{ x: '-100vw' }} // Start off-screen to the left
                    animate={{ x: 0 }} // Animate to original position
                    transition={{ type: 'spring', stiffness: 120 }}
                    className={styles.chatbotTitlePlaceholder}
                >
                </motion.h1>
                <div className={styles.bannerPlaceholder}></div>
                <SignUpButton onClick={handleSignUpClick} text={"Accept Invitation"} />
            </Stack>
        </div>
    );
};

export default HomePage;
