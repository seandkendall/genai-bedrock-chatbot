import '@aws-amplify/ui-react/styles.css';
import { signInWithRedirect } from 'aws-amplify/auth';

const LoginPage = () => {
    return (
        <div className='login-button-wrapper'>
            <button className='login-button' onClick={() => signInWithRedirect({ provider: 'mocksaml' })}>
                Log in with SAML
            </button>
        </div>
    );
};

export default LoginPage;
