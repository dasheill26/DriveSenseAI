const canvas = document.getElementById("clusterCanvas");
const ctx = canvas.getContext("2d");

let speed = 0;
let rpm = 800;

let targetSpeed = 0;
let targetRPM = 800;

let startupSweep = true;
let sweepProgress = 0;

let fuel = 82;
let targetFuel = 82;

let coolant = 90;
let targetCoolant = 90;

let engineLoad = 18;
let throttle = 18;

let oil = 94;
let battery = 13.8;
let range = 320;

let outsideTemp = 12;
let tripA = 124.6;
let instantMPG = 32;
let avgMPG = 36.4;

let gear = "P";
let driveMode = "COMFORT";
let brightness = "NIGHT";

let connected = false;
let demoMode = true;
let apiStatus = "DEMO";

const driveModeBtn = document.getElementById("driveModeBtn");
const brightnessBtn = document.getElementById("brightnessBtn");

if (driveModeBtn) {
    driveModeBtn.onclick = () => {
        driveMode = driveMode === "COMFORT" ? "SPORT" : "COMFORT";
        driveModeBtn.textContent = "Drive Mode: " + driveMode;
    };
}

if (brightnessBtn) {
    brightnessBtn.onclick = () => {
        brightness = brightness === "NIGHT" ? "DAY" : "NIGHT";
        brightnessBtn.textContent = "Brightness: " + brightness;
    };
}

function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
}

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function safeNumber(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}

function mapAngle(val, min, max) {
    const start = Math.PI * 0.78;
    const end = Math.PI * 2.22;
    const pct = clamp((val - min) / (max - min), 0, 1);
    return start + pct * (end - start);
}

function drawText(text, x, y, size, color = "#fff", weight = "600", align = "center") {
    ctx.font = `${weight} ${size}px Segoe UI`;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
}

async function fetchLiveData() {
    try {
        const res = await fetch("/api/live_data");
        const data = await res.json();

        if (!data.ok) {
            apiStatus = "DEMO";
            demoMode = true;
            connected = false;
            return;
        }

        targetRPM = clamp(safeNumber(data.rpm, 820), 0, 7000);
        targetSpeed = clamp(safeNumber(data.speed, 0), 0, 160);
        targetCoolant = clamp(safeNumber(data.coolant_temp, 91), 0, 130);
        engineLoad = clamp(safeNumber(data.engine_load, 18), 0, 100);
        throttle = clamp(safeNumber(data.throttle, 18), 0, 100);
        targetFuel = clamp(safeNumber(data.fuel_level, 82), 0, 100);

        connected = Boolean(data.connected);
        demoMode = Boolean(data.demo_mode);
        apiStatus = connected ? "LIVE OBD" : "DEMO DATA";

        gear = targetSpeed > 1 ? "D" : "P";

    } catch (err) {

        apiStatus = "OFFLINE";
        demoMode = true;
        connected = false;
    }
}

setInterval(fetchLiveData, 1200);
fetchLiveData();

/* ---------------- BACKGROUND ---------------- */

function drawBackground() {

    const bg = ctx.createLinearGradient(0, 0, 0, canvas.height);

    if (brightness === "DAY") {
        bg.addColorStop(0, "#111827");
        bg.addColorStop(1, "#05080c");
    } else {
        bg.addColorStop(0, "#03060a");
        bg.addColorStop(1, "#000000");
    }

    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const glow = ctx.createRadialGradient(700, 300, 80, 700, 300, 760);

    glow.addColorStop(0, "rgba(0,200,255,0.10)");
    glow.addColorStop(0.45, "rgba(0,255,150,0.035)");
    glow.addColorStop(1, "rgba(0,0,0,0)");

    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 2;

    ctx.strokeRect(
        24,
        24,
        canvas.width - 48,
        canvas.height - 48
    );
}

/* ---------------- GAUGE ---------------- */

function drawGauge(cx, cy, r, min, max, val, label, unit, redline = null, divide = 1) {

    const accent =
        driveMode === "SPORT"
            ? "#ff3b3b"
            : "#00c8ff";

    ctx.save();

    ctx.shadowBlur = 35;
    ctx.shadowColor = "rgba(0,0,0,0.9)";

    ctx.beginPath();
    ctx.arc(cx, cy, r + 38, 0, Math.PI * 2);

    ctx.fillStyle = "#05070a";
    ctx.fill();

    ctx.shadowBlur = 0;

    const dial = ctx.createRadialGradient(
        cx,
        cy,
        20,
        cx,
        cy,
        r + 20
    );

    dial.addColorStop(0, "#171b20");
    dial.addColorStop(0.6, "#07090d");
    dial.addColorStop(1, "#000");

    ctx.beginPath();
    ctx.arc(cx, cy, r + 20, 0, Math.PI * 2);

    ctx.fillStyle = dial;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI * 0.78, Math.PI * 2.22);

    ctx.strokeStyle = "rgba(255,255,255,0.16)";
    ctx.lineWidth = 8;
    ctx.stroke();

    const valueAngle = mapAngle(val, min, max);

    ctx.shadowBlur = 18;
    ctx.shadowColor = accent;

    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI * 0.78, valueAngle);

    ctx.strokeStyle = accent;
    ctx.lineWidth = 8;
    ctx.lineCap = "round";

    ctx.stroke();

    ctx.shadowBlur = 0;

    if (redline !== null) {

        ctx.beginPath();

        ctx.arc(
            cx,
            cy,
            r,
            mapAngle(redline, min, max),
            Math.PI * 2.22
        );

        ctx.strokeStyle = "#ff2d2d";
        ctx.lineWidth = 9;
        ctx.lineCap = "round";

        ctx.stroke();
    }

    const tickStep = max === 160 ? 5 : 250;
    const majorStep = max === 160 ? 20 : 1000;

    for (let i = min; i <= max; i += tickStep) {

        const a = mapAngle(i, min, max);

        const isMajor = i % majorStep === 0;

        const outer = r + 6;

        const inner =
            r - (
                isMajor
                    ? 28
                    : 16
            );

        ctx.beginPath();

        ctx.moveTo(
            cx + Math.cos(a) * outer,
            cy + Math.sin(a) * outer
        );

        ctx.lineTo(
            cx + Math.cos(a) * inner,
            cy + Math.sin(a) * inner
        );

        ctx.strokeStyle =
            isMajor
                ? "rgba(255,255,255,0.95)"
                : "rgba(255,255,255,0.38)";

        ctx.lineWidth =
            isMajor
                ? 3
                : 1;

        ctx.stroke();

        if (isMajor) {

            drawText(
                String(i / divide),
                cx + Math.cos(a) * (r - 58),
                cy + Math.sin(a) * (r - 58),
                22,
                "#f7f7f7",
                "700"
            );
        }
    }

    ctx.shadowBlur = 18;
    ctx.shadowColor = "rgba(255,255,255,0.85)";

    ctx.beginPath();

    ctx.moveTo(cx, cy);

    ctx.lineTo(
        cx + Math.cos(valueAngle) * (r - 56),
        cy + Math.sin(valueAngle) * (r - 56)
    );

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 4;
    ctx.lineCap = "round";

    ctx.stroke();

    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.arc(cx, cy, 9, 0, Math.PI * 2);

    ctx.fillStyle = "#ffffff";
    ctx.fill();

    drawText(
        label,
        cx,
        cy + 110,
        18,
        "rgba(255,255,255,0.72)",
        "600"
    );

    drawText(
        unit,
        cx,
        cy + 135,
        13,
        "rgba(255,255,255,0.45)",
        "500"
    );

    ctx.restore();
}

/* ---------------- SMALL CAR ---------------- */

function drawMiniCar(cx, cy) {

    ctx.save();

    ctx.fillStyle = "#d9d9d9";
    ctx.strokeStyle = "rgba(255,255,255,0.25)";
    ctx.lineWidth = 1.5;

    ctx.beginPath();
    ctx.roundRect(cx - 16, cy - 38, 32, 76, 10);

    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#111827";

    ctx.beginPath();
    ctx.roundRect(cx - 10, cy - 25, 20, 18, 6);

    ctx.fill();

    ctx.beginPath();
    ctx.roundRect(cx - 10, cy + 7, 20, 18, 6);

    ctx.fill();

    function tyre(x, y) {

        ctx.fillStyle = "#00ff9d";

        ctx.beginPath();
        ctx.roundRect(x, y, 5, 16, 3);

        ctx.fill();
    }

    tyre(cx - 23, cy - 26);
    tyre(cx + 18, cy - 26);

    tyre(cx - 23, cy + 10);
    tyre(cx + 18, cy + 10);

    ctx.restore();
}

/* ---------------- CENTER DISPLAY ---------------- */

function drawCenter() {

    const cx = 700;
    const cy = 300;

    ctx.save();

    drawText(
        "DriveSense",
        cx,
        70,
        24,
        "rgba(255,255,255,0.86)",
        "800"
    );

    drawText(
        "BMW F-Series Live Cluster",
        cx,
        98,
        14,
        "rgba(255,255,255,0.45)",
        "500"
    );

    const statusColor =
        connected
            ? "#00ff9d"
            : demoMode
                ? "#ffd166"
                : "#ff4d4d";

    drawText(
        apiStatus,
        cx,
        125,
        13,
        statusColor,
        "800"
    );

    ctx.shadowBlur = 24;
    ctx.shadowColor = "#ffffff";

    drawText(
        Math.round(speed),
        cx,
        cy - 124,
        76,
        "#ffffff",
        "800"
    );

    ctx.shadowBlur = 0;

    drawText(
        "mph",
        cx,
        cy - 82,
        17,
        "rgba(255,255,255,0.58)",
        "500"
    );

    drawText(
        "Gear " + gear,
        cx,
        cy - 48,
        22,
        "#ffffff",
        "700"
    );

    const modeColor =
        driveMode === "SPORT"
            ? "#ff3b3b"
            : "#00ff9d";

    drawText(
        driveMode,
        cx,
        cy - 18,
        15,
        modeColor,
        "800"
    );

    /* SMALLER CAR */

    drawMiniCar(cx, cy + 72);

    /* TYRE PSI */

    drawText("FL", cx - 78, cy + 38, 14, "#00c8ff", "800");
    drawText("35", cx - 78, cy + 60, 26, "#ffffff", "800");
    drawText("PSI", cx - 78, cy + 84, 12, "rgba(255,255,255,.55)");

    drawText("FR", cx + 78, cy + 38, 14, "#00c8ff", "800");
    drawText("35", cx + 78, cy + 60, 26, "#ffffff", "800");
    drawText("PSI", cx + 78, cy + 84, 12, "rgba(255,255,255,.55)");

    drawText("RL", cx - 78, cy + 122, 14, "#00c8ff", "800");
    drawText("35", cx - 78, cy + 144, 26, "#ffffff", "800");
    drawText("PSI", cx - 78, cy + 168, 12, "rgba(255,255,255,.55)");

    drawText("RR", cx + 78, cy + 122, 14, "#00c8ff", "800");
    drawText("35", cx + 78, cy + 144, 26, "#ffffff", "800");
    drawText("PSI", cx + 78, cy + 168, 12, "rgba(255,255,255,.55)");

    ctx.restore();
}

/* ---------------- UPDATE ---------------- */

function updateValues() {

    if (startupSweep) return;

    rpm = lerp(rpm, targetRPM, 0.08);
    speed = lerp(speed, targetSpeed, 0.08);

    coolant =
        lerp(
            coolant,
            targetCoolant,
            0.05
        );

    fuel =
        lerp(
            fuel,
            targetFuel,
            0.03
        );

    oil =
        lerp(
            oil,
            coolant + 3,
            0.025
        );

    range =
        Math.floor(fuel * 4);

    instantMPG =
        clamp(
            45 - engineLoad * 0.25 + Math.random() * 2,
            8,
            55
        );

    avgMPG =
        lerp(
            avgMPG,
            instantMPG,
            0.01
        );
}

/* ---------------- DRAW ---------------- */

function draw() {

    drawBackground();

    drawGauge(
        350,
        300,
        222,
        0,
        160,
        speed,
        "Speed",
        "mph"
    );

    drawGauge(
        1050,
        300,
        222,
        0,
        7000,
        rpm,
        "Engine Speed",
        "RPM x1000",
        6000,
        1000
    );

    drawCenter();

    ctx.save();

    ctx.globalAlpha = 0.18;
    ctx.strokeStyle = "#00c8ff";
    ctx.lineWidth = 1;

    for (let i = 0; i < 12; i++) {

        ctx.beginPath();

        ctx.moveTo(520 + i * 15, 130);
        ctx.lineTo(540 + i * 15, 130);

        ctx.stroke();
    }

    ctx.restore();
}

/* ---------------- ANIMATION ---------------- */

function animate() {

    if (startupSweep) {

        sweepProgress += 0.025;

        speed =
            160 * Math.sin(sweepProgress);

        rpm =
            7000 * Math.sin(sweepProgress);

        if (sweepProgress >= Math.PI) {

            startupSweep = false;

            speed = 0;
            rpm = 800;
        }

    } else {

        updateValues();
    }

    draw();

    requestAnimationFrame(animate);
}

animate();