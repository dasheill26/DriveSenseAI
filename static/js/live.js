let speed = 0;
let rpm = 0;
let fuel = 70;
let coolant = 50;
let gear = "P";

function updateCluster() {

    // Animate demo driving effect
    speed = Math.floor(Math.random() * 120);
    rpm = Math.floor(Math.random() * 7);
    fuel = Math.max(10, fuel - 0.05);
    coolant = 40 + Math.random() * 30;

    if (speed > 0) gear = "D";
    else gear = "P";

    // Convert to needle rotation
    let speedRotation = -120 + (speed / 160) * 240;
    let rpmRotation = -120 + (rpm / 7) * 240;

    document.getElementById("speedNeedle").style.transform =
        `rotate(${speedRotation}deg)`;

    document.getElementById("rpmNeedle").style.transform =
        `rotate(${rpmRotation}deg)`;

    document.getElementById("speedValue").innerText = speed;
    document.getElementById("rpmValue").innerText = rpm;

    document.getElementById("fuelFill").style.width = fuel + "%";
    document.getElementById("coolantFill").style.width = coolant + "%";
    document.getElementById("gear").innerText = gear;
}

setInterval(updateCluster, 800);