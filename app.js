const waveformCanvas = document.getElementById('waveformCanvas');
const waveformCtx = waveformCanvas.getContext('2d');

socket.on('waveform_data', function(data) {
    const waveform = data.waveform;


    waveformCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);

    const width = waveformCanvas.width;
    const height = waveformCanvas.height;
    const midY = height / 2;

    waveformCtx.beginPath();
    waveformCtx.moveTo(0, midY);
    waveform.forEach((value, index) => {
        const x = (index / waveform.length) * width;
        const y = midY - (value * midY); 
        waveformCtx.lineTo(x, y);
    });

    waveformCtx.strokeStyle = 'lightblue';
    waveformCtx.stroke();
});
socket.on('note_detected', function(data) {
    const pitch = data.note; // Use the detected pitch or calculate a "speed" from it
    const speed = Math.max(2, 10 - (pitch / 100)); // Adjust speed calculation as needed

    document.querySelectorAll('.wave').forEach(wave => {
        wave.style.animationDuration = `${speed}s`;
    });
});
