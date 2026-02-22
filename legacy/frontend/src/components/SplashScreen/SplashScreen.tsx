import './SplashScreen.css';
import uc_ai_icon from "../../assets/ari_logo_new.png";

const SplashScreen = () => {
  return (
    <div className="splash">
      <img src={uc_ai_icon} alt="ARI Logo" className="splash_logo" />
      {/* <h3 className="tagline">Powering Real Estate AI...</h3> */}
      <div className="loading-bar">
        <div className="loading-fill"></div>
      </div>
    </div>
  );
};

export default SplashScreen;