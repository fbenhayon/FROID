export const RTC_CONFIG: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

export function createConferenceStream(source: MediaStream) {
  const stream = new MediaStream();
  const audioTrack = source
    .getAudioTracks()
    .find((track) => track.readyState === "live");
  const videoTrack = source
    .getVideoTracks()
    .find((track) => track.readyState === "live");

  if (audioTrack) stream.addTrack(audioTrack);
  if (videoTrack) stream.addTrack(videoTrack);
  return stream;
}
