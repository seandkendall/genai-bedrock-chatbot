import React, {
	useState,
	useRef,
	forwardRef,
	useImperativeHandle,
} from "react";
import { Box, TextField, IconButton, Typography } from "@mui/material";
import { FaPaperPlane, FaPaperclip, FaTimes } from "react-icons/fa";
import axios from "axios";

const MAX_CONTENT_ITEMS = 20;
const MAX_IMAGES = 20;
const MAX_DOCUMENTS = 5;
const MAX_IMAGE_SIZE = 3.75 * 1024 * 1024; // 3.75 MB
const MAX_IMAGE_DIMENSION = 8000; // 8000 px
const MAX_DOCUMENT_SIZE = 4.5 * 1024 * 1024; // 4.5 MB
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

export const getPlaceholderText = (selectedMode, selectedKbMode) => {
	if (!selectedMode || !selectedMode.category) {
		return "Select a Model, Agent, KnowledgeBase or PromptFlow in the Header";
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
			appSessionid,
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
		const isImageFile = (file) => {
			const imageTypes = [
				"image/png",
				"image/jpeg",
				"image/jpg",
				"image/gif",
				"image/webp",
			];
			return imageTypes.includes(file.type);
		};
		const handleFiles = (files) => {
			const newAttachments = [];

			for (const file of files) {
				if (attachments.length + newAttachments.length >= MAX_CONTENT_ITEMS) {
					alert(
						`You can only attach up to ${MAX_CONTENT_ITEMS} items in total.`,
					);
					break;
				}
				//does the file already exist?
				if (
					attachments.some((attachment) => attachment.name === file.name) ||
					uploadedFileNames.includes(file.name)
				) {
					// File name already exists, alert the user
					alert(
						`A file named "${file.name}" has already been uploaded. Please rename the file and try again.`,
					);
					continue;
				}

				const fileExtension = file.name.split(".").pop().toLowerCase();
				const isImage = ["png", "jpeg", "jpg", "gif", "webp"].includes(
					fileExtension,
				);
				const isDocument = ALLOWED_DOCUMENT_TYPES.includes(fileExtension);

				// Block docx files with the specific MIME type
				if (
					fileExtension === "docx" &&
					file.type ===
						"application/vnd.openxmlformats-officedocument.wordprocessingml.document"
				) {
					alert(`File type not allowed: ${file.type}`);
					continue;
				}

				if (isImage && !selectedMode.allow_input_image) {
					alert("Image uploads are not allowed for this mode.");
					continue;
				}

				if (isDocument && !selectedMode.allow_input_document) {
					alert("Document uploads are not allowed for this mode.");
					continue;
				}

				if (!isImage && !isDocument) {
					alert(`File type not allowed: ${file.name}`);
					continue;
				}

				if (isImage) {
					if (
						attachments.filter((a) => a.type.startsWith("image/")).length +
							newAttachments.filter((a) => a.type.startsWith("image/"))
								.length >=
						MAX_IMAGES
					) {
						alert(`You can only attach up to ${MAX_IMAGES} images.`);
						continue;
					}

					if (file.size > MAX_IMAGE_SIZE) {
						alert(`Image size must be no more than 3.75 MB: ${file.name}`);
						continue;
					}

					const reader = new FileReader();
					reader.onload = () => {
						const img = new Image();
						img.onload = () => {
							URL.revokeObjectURL(img.src);
							if (
								img.width > MAX_IMAGE_DIMENSION ||
								img.height > MAX_IMAGE_DIMENSION
							) {
								alert(
									`Image dimensions must be no more than 8000x8000 pixels: ${file.name}`,
								);
								return;
							}
							newAttachments.push(file);
						};
						img.src = reader.result;
					};
					reader.readAsDataURL(file);
				} else {
					if (
						attachments.filter((a) => !a.type.startsWith("image/")).length +
							newAttachments.filter((a) => !a.type.startsWith("image/"))
								.length >=
						MAX_DOCUMENTS
					) {
						alert(`You can only attach up to ${MAX_DOCUMENTS} documents.`);
						continue;
					}

					if (file.size > MAX_DOCUMENT_SIZE) {
						alert(`Document size must be no more than 4.5 MB: ${file.name}`);
						continue;
					}

					newAttachments.push(file);
				}
			}
			setAttachments([...attachments, ...newAttachments]);
			setUploadedFileNames([
				...uploadedFileNames,
				...newAttachments.map((file) => file.name),
			]);
		};

		const handleFileChange = (event) => {
			const files = Array.from(event.target.files);
			handleFiles(files);
		};

		const handleRemoveAttachment = (index) => {
			const removedAttachment = attachments[index];
			setAttachments(attachments.filter((_, i) => i !== index));
			setUploadedFileNames(
				uploadedFileNames.filter((name) => name !== removedAttachment.name),
			);
		};

		const handleSend = async () => {
			if (message.trim() || attachments.length > 0) {
				if (attachments.length > 0) {
					setIsRefreshingMessage("Uploading Files to Conversation. ");
					setIsRefreshing(true);
				}
				setIsDisabled(true);
				const uploadedAttachments = await Promise.all(
					attachments.map(uploadFileToS3),
				);
				onSend(
					message.trim() ? message.trim() : "?",
					uploadedAttachments,
					false,
				);
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
			try {
				const { accessToken, idToken } = await getCurrentSession();

				const response = await axios.post(
					"/rest/get-presigned-url",
					{
						accessToken: accessToken,
						fileName: file.name,
						fileType: file.type,
						session_id: appSessionid,
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
				Object.keys(fields).forEach((key) => formData.append(key, fields[key]));
				formData.append("file", file);
				await axios.post(url, formData);
				return {
					name: sanitizeFileName(file.name),
					type: file.type,
					url: `${url}${fields.key}`,
				};
			} catch (error) {
				console.error("Error uploading file:", error);
				throw error;
			}
		};

		const isDisabled = () => {
			return (
				disabled ||
				!selectedMode ||
				(selectedMode &&
					selectedMode.category &&
					selectedMode.category === "Bedrock KnowledgeBases" &&
					!selectedKbMode)
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
			selectedMode?.allow_input_image || selectedMode?.allow_input_document;

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
						{attachments.map((file, index) => (
							<Box
								key={index}
								sx={{
									display: "flex",
									alignItems: "center",
									backgroundColor: isImageFile(file)
										? "lightgreen"
										: "lightblue",
									borderRadius: "16px",
									padding: "4px 8px",
									maxWidth: "200px",
								}}
							>
								<Typography
									variant="body2"
									sx={{
										whiteSpace: "nowrap",
										overflow: "hidden",
										textOverflow: "ellipsis",
										marginRight: "4px",
									}}
								>
									{file.name}
								</Typography>
								<IconButton
									disabled={isDisabled()}
									onClick={() => handleRemoveAttachment(index)}
									size="small"
									sx={{ padding: 0 }}
								>
									<FaTimes />
								</IconButton>
							</Box>
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
						fullWidth
						variant="outlined"
						slotProps={{
							htmlInput: {
								...(selectedMode?.category === "Bedrock Image Models" && {
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
						accept={`${selectedMode?.allow_input_image ? "image/png,image/jpeg,image/gif,image/webp," : ""}${selectedMode?.allow_input_document ? ".pdf,.csv,.doc,.docx,.xls,.xlsx,.html,.txt,.md" : ""}`}
					/>
					<IconButton
						onClick={handleAttachmentClick}
						disabled={isDisabled() || attachments.length >= MAX_CONTENT_ITEMS}
						aria-label="Attach file"
						sx={{
							display:
								selectedMode?.allow_input_image ||
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
