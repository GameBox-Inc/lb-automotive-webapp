# Audio Playback Runbook

**Last Updated:** March 2026  
**Related:** [Audio Playback Failure](audio-playback-failure.md) | [Twilio Debugging](twilio-debugging.md)

---

## Quick Checks

```bash
npm run debug:twiml   # Validate TwiML structure
npm run debug:audio  # Check audio assets in repo
```

---

## Checklist

1. **Media URL is public/reachable**
   - Twilio fetches from its servers; localhost won't work
   - Test: `curl -I <media_url>` from a public context

2. **Content-Type is correct**
   - `audio/mpeg` for MP3, `audio/wav` for WAV
   - Twilio expects standard MIME types

3. **`<Play>` URL is absolute**
   - Full URL: `https://example.com/audio/prompt.mp3`
   - Relative URLs fail

4. **No auth wall**
   - Media must be publicly accessible or use signed URLs
   - Auth headers/cookies block Twilio

5. **Format compatibility**
   - Supported: MP3, WAV, GSM, ulaw, alaw
   - Check sample rate, bitrate, codec

6. **Fallback**
   - Consider `<Say>` fallback if `<Play>` fails

---

## See Also

[Audio Playback Failure](audio-playback-failure.md) — Detailed checklist for playback failures.
