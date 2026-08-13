// app/static/js/main.js

(function () {
  "use strict";

  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  function escapeHTML(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function nowTime() {
    const d = new Date();
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  async function safeJsonFetch(url, options) {
    try {
      const res = await fetch(url, options);
      const text = await res.text();

      try {
        return JSON.parse(text);
      } catch {
        console.error("Not JSON:", text);
        return {
          ok: false,
          error: "Server returned invalid JSON",
        };
      }
    } catch (err) {
      console.error("Fetch failed:", err);
      return {
        ok: false,
        error: err.message,
      };
    }
  }

  function appendMsg(container, who, msg) {
    const row = document.createElement("div");
    row.className = `msgRow ${who}`;

    const bubble = document.createElement("div");
    bubble.className = "msgBubble";

    bubble.innerHTML = `
      <div class="msgTop">
        <span class="msgWho">${who === "user" ? "You" : "DriveSense AI"}</span>
        <span class="msgTime">${nowTime()}</span>
      </div>
      <div class="msgText">${escapeHTML(msg)}</div>
    `;

    row.appendChild(bubble);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;

    return row;
  }

  function bindAIChat() {
    const messagesEl = $("#chatMessages");
    const inputEl = $("#chatInput");
    const sendBtn = $("#chatSend");
    const imageInput = $("#imageInput");

    if (!messagesEl) return;

    if (!messagesEl.dataset.loaded) {
      appendMsg(
        messagesEl,
        "bot",
        "Upload an image or ask me anything about your car."
      );
      messagesEl.dataset.loaded = "true";
    }

    async function sendMessage(text) {
      if (!text || !text.trim()) return;

      appendMsg(messagesEl, "user", text);

      if (inputEl) {
        inputEl.value = "";
      }

      const thinkingRow = appendMsg(messagesEl, "bot", "Thinking...");

      const res = await safeJsonFetch("/api/ai_chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
        }),
      });

      thinkingRow.remove();

      if (!res.ok) {
        appendMsg(messagesEl, "bot", "❌ " + (res.error || "AI chat failed."));
        return;
      }

      appendMsg(messagesEl, "bot", res.answer || "No response received.");
    }

    if (sendBtn) {
      sendBtn.addEventListener("click", function () {
        sendMessage(inputEl ? inputEl.value : "");
      });
    }

    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          sendMessage(inputEl.value);
        }
      });
    }

    if (imageInput) {
      imageInput.addEventListener("change", function () {
        const file = imageInput.files[0];

        if (!file) return;

        if (!file.type.startsWith("image/")) {
          appendMsg(messagesEl, "bot", "❌ Please upload an image file.");
          return;
        }

        appendMsg(messagesEl, "user", "📷 Image uploaded");

        const uploadRow = appendMsg(messagesEl, "bot", "🔍 Sending image to AI...");

        const reader = new FileReader();

        reader.onload = async function () {
          const imgRes = await safeJsonFetch("/api/image_analyze", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              image: reader.result,
            }),
          });

          uploadRow.remove();

          if (!imgRes || !imgRes.ok) {
            appendMsg(
              messagesEl,
              "bot",
              "❌ Image analysis failed: " + (imgRes?.error || "Unknown error")
            );
            return;
          }

          const imageResult = imgRes.result || imgRes.answer || "Image processed.";

          appendMsg(messagesEl, "bot", "✅ Image successfully processed");
          appendMsg(messagesEl, "bot", "🧠 I see: " + imageResult);

          const explainRow = appendMsg(messagesEl, "bot", "🤖 Explaining image findings...");

          const aiRes = await safeJsonFetch("/api/ai_chat", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              message: "Explain this vehicle image result clearly for a car owner: " + imageResult,
            }),
          });

          explainRow.remove();

          if (!aiRes || !aiRes.ok) {
            appendMsg(
              messagesEl,
              "bot",
              "❌ AI explanation failed: " + (aiRes?.error || "Unknown error")
            );
            return;
          }

          appendMsg(messagesEl, "bot", aiRes.answer || "Image explanation complete.");
        };

        reader.onerror = function () {
          uploadRow.remove();
          appendMsg(messagesEl, "bot", "❌ Could not read the uploaded image.");
        };

        reader.readAsDataURL(file);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", bindAIChat);
})();