// src/components/QRCodePopup.js
import React, { useEffect, useRef } from "react";
import { Box, Modal, Typography } from "@mui/material";
import { QRCodeSVG } from "qrcode.react";

const QRCodePopup = ({ open, onClose }) => {
	const currentUrl = window.location.href;
	const modalRef = useRef(null);

	useEffect(() => {
		const handleClickOutside = (event) => {
			if (modalRef.current && open) {
				onClose();
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
		};
	}, [onClose, open]);

	return (
		<Modal
			open={open}
			onClose={onClose}
			aria-labelledby="qr-code-title"
			aria-describedby="qr-code-description"
		>
			<Box
				ref={modalRef}
				sx={{
					position: "absolute",
					top: "50%",
					left: "50%",
					transform: "translate(-50%, -50%)",
					width: 300,
					bgcolor: "background.paper",
					border: "2px solid #000",
					boxShadow: 24,
					p: 4,
					display: "flex",
					flexDirection: "column",
					alignItems: "center",
					borderRadius: 2,
				}}
			>
				<Typography
					id="qr-code-title"
					variant="h6"
					component="h2"
					sx={{ mb: 2 }}
				>
					Scan to visit this site
				</Typography>
				<QRCodeSVG value={currentUrl} size={200} />
				<Typography id="qr-code-description" variant="body2" sx={{ mt: 2 }}>
					Click anywhere to close
				</Typography>
			</Box>
		</Modal>
	);
};

export default QRCodePopup;
