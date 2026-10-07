// Shared microphone lifecycle for both launchers and the reading room.
let micState = "idle", micEpoch = 0, micTimer = null, micStopRequested = false;
let micButton = null, micTarget = null, micBase = "";

async function stopMic() {
  if (micState !== "recording") return;
  micState = "stopping";
  ++micEpoch; // Invalidate captions already awaiting a bridge response.
  clearInterval(micTimer);
  micTimer = null;
  const btn = micButton, target = micTarget, base = micBase;
  btn.classList.remove("rec");
  btn.classList.add("busy");
  btn.title = "Microphone off — finishing transcript";
  target.classList.remove("live");
  try {
    const result = await pywebview.api.stop_dictation();
    if (result.error) throw new Error(result.error);
    if (result.text) target.value = (base ? base + " " : "") + result.text;
    target.dispatchEvent(new Event("input"));
    btn.title = "Dictate";
  } catch (error) {
    btn.title = error.message || "Could not finish dictation";
  } finally {
    btn.classList.remove("busy");
    micState = "idle";
  }
}

async function toggleMic(btn, targetId) {
  if (micState === "stopping") return;
  if (micState === "starting") { micStopRequested = true; return; }
  if (micState === "recording") return stopMic();

  micState = "starting";
  micStopRequested = false;
  micButton = btn;
  micTarget = document.getElementById(targetId);
  micBase = micTarget.value.trimEnd();
  const epoch = ++micEpoch;
  btn.classList.add("busy");
  btn.classList.add("starting");
  btn.title = "Starting microphone — click again to cancel";
  try {
    const result = await pywebview.api.start_dictation();
    if (result.error) throw new Error(result.error);
    micState = "recording";
    btn.classList.remove("busy");
    btn.classList.remove("starting");
    btn.classList.add("rec");
    btn.title = "Stop dictation";
    micTarget.classList.add("live");
    if (micStopRequested) return await stopMic();
    let polling = false;
    micTimer = setInterval(async () => {
      if (polling || micState !== "recording" || epoch !== micEpoch) return;
      polling = true;
      try {
        const partial = await pywebview.api.dictation_partial();
        if (micState !== "recording" || epoch !== micEpoch) return;
        if (partial.recording === false) return await stopMic();
        if (partial.text) {
          micTarget.value = (micBase ? micBase + " " : "") + partial.text;
          micTarget.scrollTop = micTarget.scrollHeight;
        }
      } catch (error) {
        if (epoch === micEpoch) await stopMic();
      } finally {
        polling = false;
      }
    }, 600);
  } catch (error) {
    btn.classList.remove("busy");
    btn.classList.remove("starting");
    btn.classList.remove("rec");
    micTarget.classList.remove("live");
    btn.title = error.message || "Could not start dictation";
    micState = "idle";
  }
}
