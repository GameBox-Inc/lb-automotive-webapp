# Audio Playback Failure Checklist

**Last Updated:** March 2026  
**Related:** [Twilio Debugging](twilio-debugging.md) | [Twilio 503](twilio-503.md)

---

## Checklist

1. **Verify media URL is public/reachable**
   - URL must be reachable from Twilio's servers (not localhost)
   - Test: `curl -I <media_url>` from a public context

2. **Confirm content-type is correct**
   - `Content-Type: audio/mpeg` for MP3, `audio/wav` for WAV, etc.
   - Twilio expects standard audio MIME types

3. **Confirm TwiML `<Play>` URL is absolute**
   - Must be full URL: `https://example.com/audio/prompt.mp3`
   - Relative URLs will fail

4. **Confirm no auth wall blocks Twilio fetch**
   - Auth headers, cookies, or IP restrictions block Twilio
   - Media must be publicly accessible or use signed URLs

5. **Check audio encoding/format compatibility**
   - Twilio supports: MP3, WAV, GSM, ulaw, alaw
   - Sample rate, bitrate, codec compatibility

6. **Check fallback behavior if media fails**
   - Does TwiML have `<Say>` fallback?
   - Error handling when `<Play>` fails

---

## Quick Commands

```bash
# Validate TwiML structure
npm run debug:twiml

# Check audio assets in repo
npm run debug:audio
```
