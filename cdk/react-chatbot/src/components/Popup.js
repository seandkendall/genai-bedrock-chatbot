import React from "react";
import { Snackbar, Alert } from "@mui/material";

const Popup = ({ message, type, onClose, showPopup, setShowPopup }) => {
	const handleClose = (event, reason) => {
		if (reason === "clickaway") {
			return;
		}
		setShowPopup(false);
		onClose();
	};

	return (
		<Snackbar
			open={showPopup}
			autoHideDuration={5000}
			onClose={handleClose}
			anchorOrigin={{ vertical: "top", horizontal: "center" }}
		>
			<Alert onClose={handleClose} severity={type} sx={{ width: "100%" }}>
				{message}
			</Alert>
		</Snackbar>
	);
};

export default Popup;
