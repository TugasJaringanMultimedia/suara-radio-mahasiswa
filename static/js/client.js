document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  const livePlayer = document.getElementById("livePlayer");
  const liveStatus = document.getElementById("live-status");
  const liveTitle = document.getElementById("live-title");
  const searchBox = document.getElementById("searchBox");
  const archiveList = document.getElementById("archive-list");

  let mediaSource;
  let sourceBuffer;
  let audioQueue = [];

  function setupLivePlayer() {
    try {
      mediaSource = new MediaSource();
      livePlayer.src = URL.createObjectURL(mediaSource);
      mediaSource.addEventListener("sourceopen", onSourceOpen);
    } catch (e) {
      console.error("MediaSource API tidak didukung.", e);
      liveStatus.textContent += " (Browser tidak mendukung streaming langsung)";
    }
  }

  function onSourceOpen() {
    sourceBuffer = mediaSource.addSourceBuffer("audio/webm; codecs=opus");
    sourceBuffer.addEventListener("updateend", () => {
      if (audioQueue.length > 0 && !sourceBuffer.updating) {
        sourceBuffer.appendBuffer(audioQueue.shift());
      }
    });
  }

  // Hanya setup jika ada player live
  if (livePlayer && livePlayer.style.display !== "none") {
    setupLivePlayer();
  }

  socket.on("live_audio", (chunk) => {
    if (!sourceBuffer) return;

    const arrayBuffer = new Uint8Array(chunk).buffer;
    if (!sourceBuffer.updating && mediaSource.readyState === "open") {
      try {
        sourceBuffer.appendBuffer(arrayBuffer);
      } catch (e) {
        console.error("Error appending buffer:", e);
      }
    } else {
      audioQueue.push(arrayBuffer);
    }
  });

  socket.on("broadcast_started", (data) => {
    alert(
      `Siaran baru dimulai: ${data.title}\nRefresh halaman untuk mendengarkan!`
    );
    window.location.reload();
  });

  socket.on("broadcast_stopped", () => {
    alert(
      "Siaran langsung telah berakhir. Halaman akan dimuat ulang untuk memperbarui arsip."
    );
    window.location.reload();
  });

  searchBox.addEventListener("input", async (e) => {
    const query = e.target.value;
    const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
    const results = await response.json();

    archiveList.innerHTML = ""; // Kosongkan daftar
    if (results.length > 0) {
      results.forEach((b) => {
        archiveList.innerHTML += `
                    <div class="archive-item">
                        <div class="archive-info">
                            <span class="title">${b.title}</span>
                            <span class="meta">${b.date} | ${b.start_time}</span>
                        </div>
                        <audio controls preload="none" src="/rekaman/${b.filename}"></audio>
                    </div>
                `;
      });
    } else {
      archiveList.innerHTML =
        '<p id="no-archives">Tidak ada rekaman ditemukan.</p>';
    }
  });
});
