# Leonardo AI Integration Setup

## Overview

This document describes how to set up Leonardo AI integration for generating static images and carousel cover slides.

## Environment Variables

Add these to your Railway deployment:

| Variable | Required | Description |
|----------|----------|-------------|
| `LEONARDO_API_KEY` | Yes | Your Leonardo AI API key |
| `LEONARDO_REFILOE_REFERENCE_ID` | No | Image ID of Refiloe reference image for character consistency |
| `LEONARDO_MODEL_ID` | No | Model ID to use (defaults to Nano Banana Pro) |

## Getting Your API Key

1. Go to [Leonardo AI](https://leonardo.ai/)
2. Sign in to your account
3. Go to Settings → API
4. Generate a new API key
5. **Webhook fields can be left blank** - we use polling instead

## Uploading Reference Image

For best character consistency:

1. In Leonardo AI, go to your profile
2. Upload your best Refiloe reference image
3. Copy the image ID from the URL or API response
4. Add it as `LEONARDO_REFILOE_REFERENCE_ID` in Railway

## Image Dimensions

All images are generated at 1080x1350 (4:5 portrait ratio) by default, optimized for mobile viewing.

## Content Type Mapping

| Content Type | Image Style |
|--------------|-------------|
| motivational | Quote graphic (no Refiloe) |
| announcement | Quote graphic (no Refiloe) |
| educational | Refiloe in home office setting |
| professional | Refiloe in co-working space |
| business | Refiloe in executive office |
| community | Refiloe in coffee shop |
| fitness | Refiloe in fitness studio |
| workout | Refiloe in gym |
| casual | Refiloe in outdoor café |
| relatable | Refiloe in cozy living room |
| outdoor | Refiloe in park |
| studio | Refiloe in group fitness studio |
| lifestyle | Refiloe in wellness corner |

## Troubleshooting

### "LEONARDO_API_KEY environment variable required"
Add your API key to Railway environment variables.

### Generation times out
Leonardo AI typically takes 10-30 seconds. If timeout occurs:
- Check your API quota
- Try a simpler prompt
- Contact Leonardo AI support if persistent

### Character doesn't look like Refiloe
Ensure `LEONARDO_REFILOE_REFERENCE_ID` is set with a high-quality reference image.
