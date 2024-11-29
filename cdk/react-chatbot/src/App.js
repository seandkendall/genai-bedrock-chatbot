// src/App.jsx

import { Routes, Route } from "react-router-dom";
import LoginPage from "./pages/Login";
import HomePage from "./pages/Home";
import LogoutPage from "./pages/Logout";
import { ProtectedRoute } from "./components/ProtectedRoute";

import "./App.css";

import amplifyConfig from './config.json';
import { Amplify } from 'aws-amplify';
Amplify.configure(amplifyConfig);
// uncomment the below lines to troubleshoot Cognito config
//const currentConfig = Amplify.getConfig();
//console.log(JSON.stringify(currentConfig, null, 2));

function App() {
    return (
        <Routes>
            <Route path="/" element={
                <ProtectedRoute>
                    <HomePage />
                </ProtectedRoute>
            }
            />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/logout/callback" element={<LogoutPage />} />
        </Routes>
    );
}

export default App;