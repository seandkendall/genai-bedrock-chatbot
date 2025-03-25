import React, {
	useState,
	useRef,
	forwardRef,
	useImperativeHandle,
	useCallback,
} from "react";
import { Box, Chip, TextField, IconButton } from "@mui/material";
import { FaPaperPlane, FaPaperclip } from "react-icons/fa";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

const MAX_CONTENT_ITEMS = 20;
const MAX_IMAGES = 20;
const MAX_VIDEOS = 1;
const MAX_DOCUMENTS = 5;
const MAX_DOCUMENT_SIZE = 4.5 * 1024 * 1024; // 4.5 MB
const MAX_VIDEO_SIZE = 1024 * 1024 * 1024; // 1 GB
const ALLOWED_DOCUMENT_TYPES = [
	"pdf",
	"csv",
	"doc",
	"docx",
	"xls",
	"xlsx",
	"html",
	"txt",
	"md",
];
const ALLOWED_VIDEO_TYPES = [
	"mov",
	"mkv",
	"mp4",
	"webm",
	"flv",
	"mpeg",
	"mpg",
	"wmv",
	"3gp",
];
const ALLOWED_IMAGE_TYPES = ["png", "jpeg", "jpg", "gif", "webp"];

export const getPlaceholderText = (selectedMode, selectedKbMode) => {
	if (!selectedMode || !selectedMode.category) {
		return "Select a Model, Agent, KnowledgeBase or PromptFlow in the Header";
	}
	if (selectedMode.category === "Bedrock Image Models") {
		return "Generate an Image of...";
	}
	if (selectedMode.category === "Bedrock Video Models") {
		return "Generate an Video of...";
	}
	return selectedMode.category === "Bedrock KnowledgeBases" && !selectedKbMode
		? "Select a Model for your KnowledgeBase in the Header"
		: "Type your message...";
};

export function sanitizeFileName(name) {
	const lastDotIndex = name.lastIndexOf(".");
	let filename;
	let extension;

	if (lastDotIndex === -1) {
		filename = name;
		extension = ".txt";
	} else {
		filename = name.slice(0, lastDotIndex).trim();
		extension = name.slice(lastDotIndex);
	}
	const sanitizedFilename = filename.replace(/[^\w\-()[\]]/g, "");
	return `${sanitizedFilename}${extension}`;
}

const MessageInput = forwardRef(
	(
		{
			selectedConversation,
			onSend,
			disabled,
			setIsDisabled,
			selectedMode,
			selectedKbMode,
			getCurrentSession,
			attachments,
			setAttachments,
			setIsRefreshing,
			setIsRefreshingMessage,
			uploadedFileNames,
			setUploadedFileNames,
		},
		ref,
	) => {
		const [message, setMessage] = useState("");
		const [isDragging, setIsDragging] = useState(false);
		const inputRef = useRef(null);
		const fileInputRef = useRef(null);

		useImperativeHandle(ref, () => ({
			focus: () => {
				if (inputRef.current) {
					inputRef.current.focus();
				}
			},
		}));

		const handleAttachmentClick = () => {
			if (fileInputRef.current) {
				fileInputRef.current.click();
			}
		};

		const isImageFile = useCallback((file) => {
			if (file instanceof File) {
				return ALLOWED_IMAGE_TYPES.includes(
					file.name.split(".").pop().toLowerCase(),
				);
			}
			return ALLOWED_IMAGE_TYPES.includes(file.split(".").pop().toLowerCase());
		}, []);

		const isVideoFile = useCallback((file) => {
			if (file instanceof File) {
				return ALLOWED_VIDEO_TYPES.includes(
					file.name.split(".").pop().toLowerCase(),
				);
			}
			return ALLOWED_VIDEO_TYPES.includes(file.split(".").pop().toLowerCase());
		}, []);

		const isDocumentFile = useCallback((file) => {
			if (file instanceof File) {
				return ALLOWED_DOCUMENT_TYPES.includes(
					file.name.split(".").pop().toLowerCase(),
				);
			}
			return ALLOWED_DOCUMENT_TYPES.includes(
				file.split(".").pop().toLowerCase(),
			);
		}, []);

		const handleFiles = async (files) => {
			const newAttachments = [];

			for (const file of files) {
				if (attachments.length + newAttachments.length >= MAX_CONTENT_ITEMS) {
					alert(
						`You can only attach up to ${MAX_CONTENT_ITEMS} items in total.`,
					);
					break;
				}

				if (
					attachments.some(
						(attachment) => attachment.file.name === file.name,
					) ||
					uploadedFileNames.includes(file.name)
				) {
					alert(
						`A file named "${file.name}" has already been uploaded. Please rename the file and try again.`,
					);
					continue;
				}

				const isImage = isImageFile(file);
				const isVideo = isVideoFile(file);
				const isDocument = isDocumentFile(file);

				if (isImage && !selectedMode.allow_input_image) {
					alert("Image uploads are not allowed for this mode.");
					continue;
				}

				if (isVideo && !selectedMode.allow_input_video) {
					alert("Video uploads are not allowed for this mode.");
					continue;
				}

				if (isDocument && !selectedMode.allow_input_document) {
					alert("Document uploads are not allowed for this mode.");
					continue;
				}

				if (!isImage && !isDocument && !isVideo) {
					alert(`File type not allowed: ${file.name}`);
					continue;
				}

				if (isImage) {
					let allowed_number_of_images = MAX_IMAGES;
					if (selectedMode.output_type.toLowerCase() === "video") {
						allowed_number_of_images = 1;
					}

					if (
						attachments.filter((a) => isImageFile(a.file)).length +
							newAttachments.filter((a) => isImageFile(a.file)).length +
							uploadedFileNames.filter((a) => isImageFile(a)).length >=
						allowed_number_of_images
					) {
						alert(
							`You can only attach up to ${allowed_number_of_images} images.`,
						);
						continue;
					}

					try {
						if (file.name === "image.jpg") {
							const timestamp = Date.now();
							const newFileName = `image-${timestamp}-${newAttachments.length}.jpg`;
							const newFile = new File([file], newFileName, {
								type: file.type,
							});
							newAttachments.push({
								id: uuidv4(),
								file: newFile,
							});
						} else {
							newAttachments.push({
								id: uuidv4(),
								file: file,
							});
						}
					} catch (error) {
						console.error("Error processing image:", error);
						alert(`Error processing image: ${file.name}`);
					}
				} else if (isVideo) {
					if (
						attachments.filter((a) => isVideoFile(a.file)).length +
							newAttachments.filter((a) => isVideoFile(a.file)).length +
							uploadedFileNames.filter((a) => isVideoFile(a)).length >=
						MAX_VIDEOS
					) {
						alert(`You can only attach up to ${MAX_VIDEOS} video.`);
						continue;
					}

					if (file.size > MAX_VIDEO_SIZE) {
						alert(`Video size must be no more than 1 GB: ${file.name}`);
						continue;
					}

					newAttachments.push({
						id: uuidv4(),
						file: file,
					});
				} else {
					if (
						attachments.filter((a) => !isImageFile(a.file)).length +
							newAttachments.filter((a) => !isImageFile(a.file)).length +
							uploadedFileNames.filter((a) => !isImageFile(a)).length >=
						MAX_DOCUMENTS
					) {
						alert(`You can only attach up to ${MAX_DOCUMENTS} documents.`);
						continue;
					}

					if (file.size > MAX_DOCUMENT_SIZE) {
						alert(`Document size must be no more than 4.5 MB: ${file.name}`);
						continue;
					}

					newAttachments.push({
						id: uuidv4(),
						file: file,
					});
				}
			}

			setAttachments([...attachments, ...newAttachments]);
			setUploadedFileNames([
				...uploadedFileNames,
				...newAttachments.map((attachment) => attachment.file.name),
			]);
		};

		const handleFileChange = (event) => {
			const files = Array.from(event.target.files);
			handleFiles(files);
		};

		const handleRemoveAttachment = (id) => {
			const attachmentToRemove = attachments.find(
				(attachment) => attachment.id === id,
			);
			setAttachments(attachments.filter((attachment) => attachment.id !== id));
			setUploadedFileNames(
				uploadedFileNames.filter(
					(name) => name !== attachmentToRemove.file.name,
				),
			);
		};

		const handleSend = async () => {
			if (message.trim() || attachments.length > 0) {
				let truncated = false;
				let finalMessage = message.trim();

				const messageSizeInBytes = new TextEncoder().encode(
					finalMessage,
				).length;
				if (messageSizeInBytes > 250 * 1024) {
					const maxAllowedBytes = 250 * 1024;
					let currentBytes = 0;
					let truncatedMessage = "";

					for (const char of finalMessage) {
						const charSize = new TextEncoder().encode(char).length;
						if (currentBytes + charSize > maxAllowedBytes) break;
						truncatedMessage += char;
						currentBytes += charSize;
					}

					finalMessage = truncatedMessage;
					truncated = true;
				}

				if (attachments.length > 0) {
					setIsRefreshingMessage("Uploading Files to Conversation. ");
					setIsRefreshing(true);
				}
				setIsDisabled(true);

				const uploadedAttachments = await Promise.all(
					attachments.map((attachment) => uploadFileToS3(attachment.file)),
				);

				onSend(
					finalMessage ? finalMessage : "?",
					uploadedAttachments,
					false,
					truncated,
				);

				setIsRefreshing(false);
				setMessage("");
				setAttachments([]);

				if (fileInputRef.current) {
					fileInputRef.current.value = "";
				}

				if (inputRef.current) {
					inputRef.current.value = "";
				}
			}
		};

		const uploadFileToS3 = async (file) => {
			const MAX_RETRIES = 3;
			const TIMEOUT_MS = 45000;

			const axiosWithTimeout = axios.create({
				timeout: TIMEOUT_MS,
			});

			let retries = 0;

			const attemptUpload = async () => {
				try {
					const { accessToken, idToken } = await getCurrentSession();

					const response = await axiosWithTimeout.post(
						"/rest/get-presigned-url",
						{
							accessToken: accessToken,
							fileName: file.name,
							fileType: file.type,
							session_id: selectedConversation?.session_id,
						},
						{
							headers: {
								Authorization: `Bearer ${idToken}`,
								"Content-Type": "application/json",
							},
						},
					);

					const { url, fields } = response.data;
					const formData = new FormData();

					for (const [key, value] of Object.entries(fields)) {
						formData.append(key, value);
					}

					formData.append("file", file);

					await axiosWithTimeout.post(url, formData);

					return {
						name: sanitizeFileName(file.name),
						type: file.type,
						url: `${url}${fields.key}`,
					};
				} catch (error) {
					if (retries < MAX_RETRIES) {
						retries++;
						console.log(`Upload attempt ${retries} failed, retrying...`);

						const waitTime = 1000 * 2 ** (retries - 1);
						await new Promise((resolve) => setTimeout(resolve, waitTime));

						return attemptUpload();
					}

					console.error(
						`Error uploading file after ${MAX_RETRIES} attempts:`,
						error,
					);
					throw error;
				}
			};

			return attemptUpload();
		};

		const isDisabled = () => {
			return (
				disabled ||
				!selectedMode ||
				(selectedMode?.category === "Bedrock KnowledgeBases" && !selectedKbMode)
			);
		};

		const handleKeyDown = (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				handleSend();
				e.preventDefault();
			} else if (e.key === "Tab") {
				e.preventDefault();
				const { selectionStart, selectionEnd } = e.target;
				const newMessage = `${message.substring(0, selectionStart)}\t${message.substring(selectionEnd)}`;
				setMessage(newMessage);
				setTimeout(() => {
					e.target.selectionStart = e.target.selectionEnd = selectionStart + 1;
				}, 0);
			}
		};

		const isDragDropEnabled =
			selectedMode?.allow_input_image ||
			selectedMode?.allow_input_document ||
			selectedMode?.allow_input_video;

		const handleDragOver = (e) => {
			if (isDragDropEnabled && !isDisabled()) {
				e.preventDefault();
				setIsDragging(true);
			}
		};

		const handleDragLeave = () => {
			if (isDragDropEnabled) {
				setIsDragging(false);
			}
		};

		const handleDrop = (e) => {
			if (isDragDropEnabled && !isDisabled()) {
				e.preventDefault();
				setIsDragging(false);
				const files = Array.from(e.dataTransfer.files);
				handleFiles(files);
			}
		};

		return (
			<Box
				sx={{
					display: "flex",
					flexDirection: "column",
					padding: 2,
					...(isDragging && {
						border: "2px dashed #007bff",
						backgroundColor: "rgba(0, 123, 255, 0.1)",
					}),
				}}
				onDragOver={handleDragOver}
				onDragLeave={handleDragLeave}
				onDrop={handleDrop}
			>
				{attachments.length > 0 && (
					<Box sx={{ mb: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
						{attachments.map((attachment) => (
							<Chip
								key={attachment.id}
								label={attachment.file.name}
								color={
									isImageFile(attachment.file)
										? "primary"
										: isVideoFile(attachment.file)
											? "secondary"
											: isDocumentFile(attachment.file)
												? "warning"
												: "success"
								}
								disabled={isDisabled()}
								onDelete={() => handleRemoveAttachment(attachment.id)}
								sx={{ ml: 1 }}
								size="small"
							/>
						))}
					</Box>
				)}

				<Box sx={{ display: "flex", alignItems: "center" }}>
					<TextField
						inputRef={inputRef}
						value={message}
						onChange={(e) => setMessage(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder={getPlaceholderText(selectedMode, selectedKbMode)}
						disabled={isDisabled()}
						multiline
						maxRows={4}
						fullWidth
						variant="outlined"
						slotProps={{
							htmlInput: {
								...((selectedMode?.category === "Bedrock Image Models" ||
									selectedMode?.category === "Bedrock Video Models") && {
									maxLength: 512,
								}),
							},
						}}
						sx={{ mr: 2 }}
					/>
					<input
						type="file"
						ref={fileInputRef}
						style={{ display: "none" }}
						onChange={handleFileChange}
						multiple
						accept={`${selectedMode?.allow_input_image ? "image/png,image/jpeg,image/jpg,image/gif,image/webp," : ""}${selectedMode?.allow_input_document ? ".pdf,.csv,.doc,.docx,.xls,.xlsx,.html,.txt,.md," : ""}${selectedMode?.allow_input_video ? "video/mp4,video/x-m4v,video/quicktime,video/x-matroska,video/webm,video/x-flv,video/mpeg,video/x-msvideo,video/3gpp," : ""}`}
					/>
					<IconButton
						onClick={handleAttachmentClick}
						disabled={isDisabled() || attachments.length >= MAX_CONTENT_ITEMS}
						aria-label="Attach file"
						sx={{
							display:
								selectedMode?.allow_input_image ||
								selectedMode?.allow_input_video ||
								selectedMode?.allow_input_document
									? "inline-flex"
									: "none",
						}}
					>
						<FaPaperclip />
					</IconButton>
					<IconButton
						onClick={handleSend}
						disabled={
							isDisabled() || (!message.trim() && attachments.length === 0)
						}
						aria-label="Send message"
					>
						<FaPaperPlane />
					</IconButton>
				</Box>
			</Box>
		);
	},
);

export default MessageInput;
