(() => {

    const chatBox = document.getElementById("chatBox");
    const input = document.getElementById("chatInput");

    const sendBtn = document.getElementById("sendBtn");
    const micBtn = document.getElementById("micBtn");

    const clearBtn = document.getElementById("clearBtn");
    const stopVoiceBtn = document.getElementById("stopVoiceBtn");

    const voiceStatus = document.getElementById("voiceStatus");
    const voiceDot = document.getElementById("voiceDot");
    const recordTimer = document.getElementById("recordTimer");

    const imageInput = document.getElementById("imageInput");
    const uploadStatus = document.getElementById("uploadStatus");
    const uploadPreview = document.getElementById("uploadPreview");

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    let timerInterval;
    let seconds = 0;

    if (!chatBox) {
        return;
    }

    function addMessage(role, text) {
        const wrapper = document.createElement("div");
        wrapper.className = `msg ${role}`;

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.innerText = text || "No response received.";

        wrapper.appendChild(bubble);
        chatBox.appendChild(wrapper);

        chatBox.scrollTop = chatBox.scrollHeight;

        return bubble;
    }

    function createThinkingBubble(text = "DriveSense is thinking") {
        const wrapper = document.createElement("div");
        wrapper.className = "msg bot";

        const bubble = document.createElement("div");
        bubble.className = "bubble";

        bubble.innerHTML = `
            <div class="thinkingWrap">
                <span>${text}</span>
                <div class="thinkingDots">
                    <div></div>
                    <div></div>
                    <div></div>
                </div>
            </div>
        `;

        wrapper.appendChild(bubble);
        chatBox.appendChild(wrapper);

        chatBox.scrollTop = chatBox.scrollHeight;

        return wrapper;
    }

    async function sendMessage(message = null) {
        const msg = message || input.value.trim();

        if (!msg) return;

        addMessage("user", msg);

        input.value = "";

        const thinking = createThinkingBubble("DriveSense is analysing");

        try {
            const response = await fetch("/api/ai_chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: msg
                })
            });

            const data = await response.json();

            thinking.remove();

            if (!data.ok) {
                addMessage("bot", data.error || "❌ AI failed to respond.");
                return;
            }

            const answer =
                data.answer ||
                data.result ||
                data.response ||
                "No AI response.";

            addMessage("bot", answer);

            speak(answer);

        } catch (err) {
            console.log(err);

            thinking.remove();

            addMessage("bot", "❌ Network error connecting to DriveSense AI.");
        }
    }

    function startTimer() {
        seconds = 0;

        if (recordTimer) {
            recordTimer.innerText = "0s";
        }

        timerInterval = setInterval(() => {
            seconds++;

            if (recordTimer) {
                recordTimer.innerText = seconds + "s";
            }
        }, 1000);
    }

    function stopTimer() {
        clearInterval(timerInterval);

        if (recordTimer) {
            recordTimer.innerText = "0s";
        }
    }

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true
            });

            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = async () => {
                if (voiceStatus) {
                    voiceStatus.innerText = "Processing speech...";
                }

                const blob = new Blob(audioChunks, {
                    type: "audio/webm"
                });

                const reader = new FileReader();

                reader.readAsDataURL(blob);

                reader.onloadend = async () => {
                    try {
                        const response = await fetch("/api/speech_to_text", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                audio: reader.result
                            })
                        });

                        const data = await response.json();

                        if (!data.ok) {
                            if (voiceStatus) {
                                voiceStatus.innerText = "Speech failed";
                            }

                            addMessage("bot", "❌ Whisper failed to transcribe.");
                            return;
                        }

                        const heard = data.text.trim();

                        if (!heard) {
                            if (voiceStatus) {
                                voiceStatus.innerText = "No speech detected";
                            }

                            return;
                        }

                        input.value = heard;

                        if (voiceStatus) {
                            voiceStatus.innerText = "✅ Heard: " + heard;
                        }

                        sendMessage(heard);

                    } catch (err) {
                        console.log(err);

                        if (voiceStatus) {
                            voiceStatus.innerText = "Voice network error";
                        }
                    }
                };
            };

            mediaRecorder.start();

            isRecording = true;

            if (micBtn) {
                micBtn.classList.add("active");
            }

            if (voiceDot) {
                voiceDot.classList.add("active");
            }

            if (voiceStatus) {
                voiceStatus.innerText = "Listening...";
            }

            startTimer();

        } catch (err) {
            console.log(err);

            if (voiceStatus) {
                voiceStatus.innerText = "Microphone permission denied";
            }
        }
    }

    function stopRecording() {
        if (!mediaRecorder) return;

        if (mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }

        isRecording = false;

        if (micBtn) {
            micBtn.classList.remove("active");
        }

        if (voiceDot) {
            voiceDot.classList.remove("active");
        }

        stopTimer();
    }

    if (micBtn) {
        micBtn.addEventListener("click", () => {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
    }

    if (imageInput) {
        imageInput.addEventListener("change", async (e) => {
            const file = e.target.files[0];

            if (!file) return;

            if (uploadStatus) {
                uploadStatus.innerText = "Uploading image...";
            }

            const previewURL = URL.createObjectURL(file);

            if (uploadPreview) {
                uploadPreview.innerHTML = `
                    <img src="${previewURL}" />
                `;
            }

            const reader = new FileReader();

            reader.readAsDataURL(file);

            reader.onloadend = async () => {
                if (uploadStatus) {
                    uploadStatus.innerText = "Analyzing vehicle image...";
                }

                addMessage("user", "📸 Uploaded vehicle image");

                const thinking = createThinkingBubble("Analyzing image with DriveSense Vision");

                try {
                    const response = await fetch("/api/image_analyze", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            image: reader.result
                        })
                    });

                    const data = await response.json();

                    thinking.remove();

                    if (!data.ok) {
                        if (uploadStatus) {
                            uploadStatus.innerText = "❌ Failed to analyze image";
                        }

                        addMessage("bot", data.error || "❌ Image analysis failed.");
                        return;
                    }

                    const imageAnswer =
                        data.result ||
                        data.answer ||
                        data.analysis ||
                        data.response ||
                        "Image analyzed, but no text response was returned.";

                    if (uploadStatus) {
                        uploadStatus.innerText = "✅ Image analyzed successfully";
                    }

                    addMessage("bot", imageAnswer);

                    speak(imageAnswer);

                } catch (err) {
                    console.log(err);

                    thinking.remove();

                    if (uploadStatus) {
                        uploadStatus.innerText = "❌ Image analysis failed";
                    }

                    addMessage("bot", "❌ Server error while analyzing image.");
                }
            };
        });
    }

    function speak(text) {
        if (!text) return;
        if (!window.speechSynthesis) return;

        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);

        utterance.lang = "en-GB";
        utterance.rate = 1;
        utterance.pitch = 1;

        window.speechSynthesis.speak(utterance);
    }

    if (stopVoiceBtn) {
        stopVoiceBtn.addEventListener("click", () => {
            if (isRecording) {
                stopRecording();
            }

            if (window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }

            if (voiceStatus) {
                voiceStatus.innerText = "Voice stopped";
            }
        });
    }

    if (sendBtn) {
        sendBtn.addEventListener("click", () => {
            sendMessage();
        });
    }

    if (input) {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                sendMessage();
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            chatBox.innerHTML = "";

            addMessage("bot", "🧠 Chat reset successfully.");
        });
    }

    document
        .querySelectorAll("[data-quick]")
        .forEach(btn => {
            btn.addEventListener("click", () => {
                sendMessage(btn.dataset.quick);
            });
        });

    addMessage(
        "bot",
        `👋 Welcome to DriveSense AI.

You can:

• Use voice assistant
• Upload vehicle images
• Diagnose engine problems
• Ask repair questions
• Get live automotive advice

Ready to assist.`
    );

})();