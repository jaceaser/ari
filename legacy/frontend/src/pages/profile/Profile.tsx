import React, { useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import styles from "./Profile.module.css";
import { Stack } from "@fluentui/react";
import { Navigate, useNavigate } from "react-router-dom";

const Profile = () => {
  const { user } = useAuth0();
  const navigate = useNavigate();

  const [profile, setProfile] = useState({
    firstName: user!.firstName || '',
    lastName: user!.lastName || '',
    email: user!.email || '',
    home_address: user!.home_address || '',
    phoneNumber: user!.phoneNumber || '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setProfile((prevProfile) => ({
      ...prevProfile,
      [name]: value,
    }));
  };

  const user_signed_up = profile.firstName == '';

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const userId = user!.sub; // Auth0 user identifier
  
    try {
          const response = await fetch('/update-profile', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              user_id: userId,
              profile_updates: profile,
            }),
          });
      
          const responseData = await response.json();
          console.log(responseData);
  
          // Handle success (e.g., show a success message)
          console.log('Profile updated successfully:', responseData);
        } catch (error) {
          console.error('Update profile error:', error);
        }

        window.location.href = 'https://portal.secure-payments.app/checkout/chkt_frm_01HNH0PJNH7CKJ8YY7EQS2A3AE';
  };

  return user_signed_up ? (
        <div className={styles.layout}>
            <Stack  verticalAlign="center" horizontalAlign="center">
                <Stack  verticalAlign="center" horizontalAlign="center">
                    <h2 className={styles.chatbotTitlePlaceholder}>Profile</h2>
                    <form onSubmit={handleSubmit}>
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <label>
                                Email:
                                <input type="email" name="email" value={profile.email} onChange={handleChange} readOnly />
                            </label>
                        </Stack>
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <label>
                                First Name:
                                <input type="text" name="firstName" value={profile.firstName} onChange={handleChange} />
                            </label>
                        </Stack>
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <label>
                                Last Name:
                                <input type="text" name="lastName" value={profile.lastName} onChange={handleChange} />
                            </label>
                        </Stack>
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <label>
                                Address:
                                <input type="text" name="address" value={profile.home_address} onChange={handleChange} />
                            </label>
                        </Stack>
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <label>
                                Phone Number:
                                <input type="tel" name="phoneNumber" value={profile.phoneNumber} onChange={handleChange} />
                            </label>
                        </Stack>
                        <div className={styles.spacer} />
                        <Stack  verticalAlign="center" horizontalAlign="center">
                            <button className={styles.updateProfileButton} type="submit">Update Profile</button>
                        </Stack>    
                    </form>
                </Stack>
            </Stack>
        </div>
  ) : <Navigate to="/chat" />;
};

export default Profile;