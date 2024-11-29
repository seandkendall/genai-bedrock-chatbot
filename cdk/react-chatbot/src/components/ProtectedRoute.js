import { Navigate } from "react-router-dom";
import { useAuthenticator } from '@aws-amplify/ui-react';
import { isFunction } from '@aws-amplify/ui';

export const ProtectedRoute = ({ children }) => {

    const { authStatus, user, signOut } = useAuthenticator((context) => [context.authStatus, context.user]);

    if (authStatus === 'configuring') {
        return 'Loading...';
    }
    else if (authStatus !== 'authenticated') {
        // user is not authenticated
        return <Navigate to="/login" />;
    }

    return (
        <>
            {isFunction(children) ? children({ signOut, user }) : children}
        </>
    );
};
