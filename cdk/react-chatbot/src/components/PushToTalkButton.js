import React, { useState, useEffect, useRef, useCallback } from "react";
import { Button, Snackbar, Alert, CircularProgress, Box } from "@mui/material";
import { Mic } from "@mui/icons-material";
import "./PushToTalkButton.css";

const PushToTalkButton = ({ onAudioData, isProcessing }) => {
	const [recordingState, setRecordingState] = useState("idle");
	const [error, setError] = useState(null);
	const mediaRecorderRef = useRef(null);
	const audioChunksRef = useRef([]);
	const streamRef = useRef(null);

	const handleAudioStop = useCallback(() => {
		try {
			const audioBlob = new Blob(audioChunksRef.current, {
				type: "audio/wav",
			});
			onAudioData(audioBlob);
			setRecordingState("processing");
		} catch (error) {
			setError("Failed to process audio recording");
			setRecordingState("idle");
		}
	}, [onAudioData]);

	useEffect(() => {
		const setupMediaRecorder = async () => {
			try {
				const stream = await navigator.mediaDevices.getUserMedia({
					audio: {
						channelCount: 1,
						sampleRate: 16000,
						echoCancellation: true,
						noiseSuppression: true,
					},
				});

				streamRef.current = stream;
				mediaRecorderRef.current = new MediaRecorder(stream);

				mediaRecorderRef.current.ondataavailable = (event) => {
					if (event.data.size > 0) {
						audioChunksRef.current.push(event.data);
					}
				};

				mediaRecorderRef.current.onstart = () => {
					audioChunksRef.current = [];
				};

				mediaRecorderRef.current.onerror = () => {
					setError("An error occurred while recording audio");
					setRecordingState("idle");
				};

				mediaRecorderRef.current.onstop = handleAudioStop;
			} catch (error) {
				let errorMessage = "Failed to access microphone";
				if (error.name === "NotAllowedError") {
					errorMessage =
						"Microphone access was denied. Please allow microphone access to use this feature.";
				} else if (error.name === "NotFoundError") {
					errorMessage =
						"No microphone found. Please connect a microphone and try again.";
				}
				setError(errorMessage);
			}
		};

		setupMediaRecorder();

		return () => {
			if (streamRef.current) {
				for (const track of streamRef.current.getTracks()) {
					track.stop();
				}
			}
		};
	}, [handleAudioStop]);

	useEffect(() => {
		if (!isProcessing && recordingState === "processing") {
			setRecordingState("idle");
		}
	}, [isProcessing, recordingState]);

	const handlePushToTalk = useCallback(() => {
		if (recordingState === "idle") {
			try {
				if (mediaRecorderRef.current?.state === "inactive") {
					setRecordingState("recording");
					mediaRecorderRef.current.start();
				}
			} catch (error) {
				setError("Failed to start recording");
				setRecordingState("idle");
			}
		} else if (recordingState === "recording") {
			try {
				if (mediaRecorderRef.current?.state === "recording") {
					mediaRecorderRef.current.stop();
				}
			} catch (error) {
				setError("Failed to stop recording");
				setRecordingState("idle");
			}
		}
	}, [recordingState]);

	const handleCloseError = () => {
		setError(null);
	};

	return (
		<Box sx={{ position: "relative", display: "inline-block" }}>
			<Button
				variant="contained"
				color={recordingState === "recording" ? "secondary" : "primary"}
				onMouseDown={recordingState === "idle" ? handlePushToTalk : undefined}
				onMouseUp={
					recordingState === "recording" ? handlePushToTalk : undefined
				}
				onTouchStart={recordingState === "idle" ? handlePushToTalk : undefined}
				onTouchEnd={
					recordingState === "recording" ? handlePushToTalk : undefined
				}
				disabled={recordingState === "processing" || isProcessing || !!error}
				className="push-to-talk-button"
				sx={{
					transition: "transform 0.2s ease",
					"&:active": {
						transform: "scale(0.95)",
					},
				}}
			>
				<Mic sx={{ fontSize: "3rem", mb: 1 }} />
				{recordingState === "recording"
					? "Release to Send"
					: recordingState === "processing"
						? "Processing..."
						: "Push to Talk"}
				{recordingState === "recording" && (
					<Box
						sx={{
							position: "absolute",
							top: -4,
							right: -4,
							width: 12,
							height: 12,
							borderRadius: "50%",
							backgroundColor: "error.main",
							animation: "pulse 1.5s infinite",
						}}
					/>
				)}
			</Button>
			{(recordingState === "processing" || isProcessing) && (
				<CircularProgress
					size={24}
					sx={{
						position: "absolute",
						top: "50%",
						left: "50%",
						marginTop: "-12px",
						marginLeft: "-12px",
					}}
				/>
			)}
			<Snackbar
				open={!!error}
				autoHideDuration={6000}
				onClose={handleCloseError}
				anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
			>
				<Alert
					onClose={handleCloseError}
					severity="error"
					variant="filled"
					sx={{ width: "100%" }}
				>
					{error}
				</Alert>
			</Snackbar>
		</Box>
	);
};

export default PushToTalkButton;
