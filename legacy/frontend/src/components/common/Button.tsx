import { CommandBarButton, DefaultButton, IButtonProps } from "@fluentui/react";

import styles from './Button.module.css';

interface ButtonProps extends IButtonProps {
  onClick: () => void;
  text: string | undefined;
}

export const ShareButton: React.FC<ButtonProps> = ({ onClick, text }) => {

  return (
    <CommandBarButton
      className={styles.shareButtonRoot}
      iconProps={{ iconName: 'Share' }}
      onClick={onClick}
      text={text}
    />
  )
}

export const HistoryButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.historyButtonRoot}
      text={text}
      iconProps={{ iconName: 'History' }}
      onClick={onClick}
    />
  )
}

export const SignUpButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.signupButtonRoot}
      text={text}
      iconProps={{ iconName: 'Login' }}
      onClick={onClick}
    />
  )
}

export const LoginButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.loginButtonRoot}
      text={text}
      iconProps={{ iconName: 'Login' }}
      onClick={onClick}
    />
  )
}

export const LogoutButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.logoutButtonRoot}
      text={text}
      iconProps={{ iconName: 'Logout' }}
      onClick={onClick}
    />
  )
}

export const UpdateProfileButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.updateProfileButtonRoot}
      text={text}
      iconProps={{ iconName: 'Update Profile' }}
      onClick={onClick}
      type="submit"
    />
  )
}