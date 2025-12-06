"""Social Media Image Generator - Generates AI influencer images using Replicate API"""
import os
import yaml
import uuid
import hashlib
import time
from io import BytesIO
import requests
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pytz
from PIL import Image, ImageStat, ImageChops
from utils.logger import log_info, log_error, log_warning
import replicate
from social_media.database import SocialMediaDatabase


class ImageGenerator:
    """Generates consistent AI influencer images for social media posts using Replicate API"""
    
    def __init__(self, config_path: str, supabase_client):
        """Initialize Replicate and load config
        
        Args:
            config_path: Path to config.yaml file
            supabase_client: Supabase client instance
        """
        try:
            # Initialize Replicate
            self.replicate_token = os.getenv('REPLICATE_API_TOKEN')
            if not self.replicate_token:
                raise ValueError("REPLICATE_API_TOKEN environment variable not set")
            
            replicate.Client(api_token=self.replicate_token)
            self.client = replicate
            
            # Initialize database service
            self.db = SocialMediaDatabase(supabase_client)
            
            # Load configuration
            self.config = self._load_config(config_path)
            
            # Set timezone
            self.sa_tz = pytz.timezone('Africa/Johannesburg')

            # Character consistency state
            self.character_reference_url: Optional[str] = None
            self._character_reference_bytes: Optional[bytes] = None
            self._character_profile = {
                "name": self.config.get('image_generation', {}).get('character_name', 'Refiloe'),
                "core_traits": (
                    "African woman in her late twenties to early thirties, athletic build,"
                    " warm confident smile, professional demeanor, poised posture,"
                    " natural textured hair with versatile styling, medium-brown skin tone"
                ),
            }

            # Prompt cache and consistency controls
            self._prompt_cache: Dict[str, Dict[str, Any]] = {}
            self._cache_ttl_seconds = self.config.get('image_generation', {}).get('cache_ttl_seconds', 3600)
            self._consistency_threshold = self.config.get('image_generation', {}).get('consistency_threshold', 45.0)
            self._negative_prompt = self.config.get('image_generation', {}).get(
                'negative_prompt',
                "blurry, distorted, disfigured, extra limbs, duplicate face, low quality, text, watermark"
            )
            self._img2img_strength = self.config.get('image_generation', {}).get('reference_strength', 0.35)
            self._flux_model = self.config.get('image_generation', {}).get(
                'flux_model',
                'black-forest-labs/flux-1.1-pro'
            )
            self._flux_version = self.config.get('image_generation', {}).get('flux_version')

            env_reference_url = os.getenv('REFILOE_REFERENCE_IMAGE_URL')
            if env_reference_url:
                if self.set_character_reference(env_reference_url):
                    log_info("Character reference loaded from environment")
                else:
                    log_warning("Failed to load character reference from environment")
            
            log_info("ImageGenerator initialized successfully")
            
        except Exception as e:
            log_error(f"Failed to initialize ImageGenerator: {str(e)}")
            raise
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file
        
        Args:
            config_path: Path to config.yaml file
            
        Returns:
            Dict: Configuration dictionary
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            log_info(f"Configuration loaded from {config_path}")
            return config
            
        except Exception as e:
            log_error(f"Failed to load config from {config_path}: {str(e)}")
            raise
    
    def generate_influencer_image(
        self,
        prompt: str,
        style: str = "professional",
        setting: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict:
        """Generate and persist an AI influencer image with character consistency.

        Args:
            prompt: Description of scene/context.
            style: Style modifier (professional, casual, workout, etc).
            setting: Specific setting or environment for the scene.
            use_cache: Whether to reuse cached generations for similar prompts.

        Returns:
            Dict: Image data containing generation details.
        """
        return self._generate_character_image(
            prompt=prompt,
            style=style,
            setting=setting,
            persist=True,
            use_cache=use_cache
        )
    
    def build_prompt(self, context: str, style: str, setting: Optional[str] = None) -> str:
        """Build complete prompt for FLUX.1 with character consistency.

        Args:
            context: Description of scene/context.
            style: Style modifier (professional, casual, workout, etc).
            setting: Specific environment or location for the scene.

        Returns:
            str: Complete prompt for the FLUX.1 model.
        """
        try:
            style = (style or "professional").lower()
            setting = (setting or self._infer_setting_from_style(style)).lower()

            base_prompt = self.config.get('image_generation', {}).get('base_prompt')
            character_core = base_prompt if base_prompt else self._character_profile['core_traits']

            style_modifiers = self._get_style_modifiers(style)
            setting_modifiers = self._get_setting_modifiers(setting)
            outfit_descriptor = self._select_outfit(style, context)

            quality_tags = (
                "ultra detailed, natural skin texture, 4k, cinematic lighting, prime lens,"
                " editorial photography, depth of field"
            )

            consistency_tags = (
                "consistent facial features: high cheekbones, expressive dark brown eyes,"
                " defined jawline, symmetrical face, medium-brown skin tone"
            )

            physique_tags = "athletic build, toned arms, confident posture"

            context_clean = context.strip().rstrip('.')

            prompt_segments = [
                character_core,
                f"{self._character_profile['name']} with a warm professional smile",
                context_clean,
                style_modifiers,
                setting_modifiers,
                outfit_descriptor,
                physique_tags,
                consistency_tags,
                quality_tags,
            ]

            full_prompt = ', '.join(filter(None, prompt_segments))
            full_prompt = self.add_lora_to_prompt(full_prompt, self.config.get('image_generation', {}).get('lora_trigger', ''))
            return full_prompt

        except Exception as e:
            log_error(f"Error building prompt: {str(e)}")
            fallback = (
                "Professional portrait of an athletic African woman, warm smile, natural hair, high quality, detailed"
            )
            return f"{fallback}, {context}"
    
    def _get_style_modifiers(self, style: str) -> str:
        """Get style-specific modifiers for the prompt."""
        style_map = {
            'professional': 'sleek tailored wardrobe, modern corporate ambience, confident demeanor, polished makeup',
            'casual': 'athleisure outfit, sunlit outdoor vibe, approachable energy, natural glow',
            'workout': 'dynamic fitness pose, studio lighting, breathable training gear, energized expression',
            'motivational': 'uplifting posture, keynote-style presence, inspirational stage lighting',
            'educational': 'interactive teaching stance, digital presentation backdrop, engaged expression',
            'social': 'community gathering, vibrant background, welcoming energy, candid smile'
        }

        return style_map.get(style.lower(), style_map['professional'])

    def _get_setting_modifiers(self, setting: str) -> str:
        """Map a high-level setting to environmental modifiers."""
        setting_map = {
            'office': 'bright coworking office, glass walls, plants, modern decor',
            'studio': 'creative studio interior, controlled lighting, textured backdrop',
            'gym': 'boutique fitness studio, equipment in background, motivational signage',
            'outdoor': 'city rooftop terrace, golden hour lighting, skyline view',
            'conference': 'conference stage, branded screen backdrop, professional audience blur',
            'classroom': 'training room, presentation screen, seated participants blurred',
            'lifestyle': 'upscale living space, soft furnishings, warm tones'
        }

        return setting_map.get(setting.lower(), setting_map['office'])

    def _infer_setting_from_style(self, style: str) -> str:
        """Infer a setting when one is not explicitly provided."""
        mapping = {
            'professional': 'office',
            'casual': 'outdoor',
            'workout': 'gym',
            'motivational': 'conference',
            'educational': 'classroom',
            'social': 'lifestyle'
        }
        return mapping.get(style.lower(), 'office')

    def _select_outfit(self, style: str, context: str) -> str:
        """Select a deterministic outfit description based on style and context."""
        outfit_map = {
            'professional': [
                'tailored navy blazer with fitted trousers and subtle jewelry',
                'sleek charcoal sheath dress with minimalist accessories',
                'soft cream blouse paired with high-waisted trousers and statement belt'
            ],
            'casual': [
                'athleisure set with cropped jacket and leggings',
                'relaxed denim jacket layered over breathable top and joggers',
                'flowy midi dress with light cardigan and sneakers'
            ],
            'workout': [
                'color-blocked training set with supportive sports bra',
                'sleek compression leggings with breathable tank top',
                'performance bodysuit with lightweight training jacket'
            ],
            'motivational': [
                'vibrant power suit with bold statement necklace',
                'structured jumpsuit with confident stance',
                'tailored blazer over monochrome ensemble with lapel mic'
            ],
            'educational': [
                'smart casual blazer with tablet in hand',
                'sleeveless blouse with tailored pants and presenter remote',
                'layered knit top with structured skirt and open notebook'
            ],
            'social': [
                'chic wrap dress with layered necklaces',
                'stylish jumpsuit with belt detail and clutch',
                'maxi skirt with fitted top and statement earrings'
            ]
        }

        options = outfit_map.get(style.lower(), outfit_map['professional'])
        if not options:
            return ''

        selector = self._hash_to_index(f"{style.lower()}|{context.strip()}", len(options))
        return f"wardrobe: {options[selector]}"

    @staticmethod
    def _hash_to_index(value: str, modulo: int) -> int:
        """Derive a deterministic index from a string."""
        digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
        return int(digest[:8], 16) % max(modulo, 1)

    def _generate_character_image(
        self,
        prompt: str,
        style: str,
        setting: Optional[str],
        persist: bool,
        use_cache: bool,
        force_refresh: bool = False
    ) -> Dict:
        """Internal pipeline for generating influencer images with consistency controls."""
        try:
            style = style or "professional"
            setting = setting or self._infer_setting_from_style(style)
            prompt_signature = self._get_prompt_signature(prompt, style, setting)

            if use_cache and not force_refresh:
                cached = self._get_cached_image(prompt_signature)
                if cached:
                    log_info(f"Cache hit for prompt signature {prompt_signature[:8]}...")
                    cached['cache_hit'] = True
                    return cached

            full_prompt = self.build_prompt(prompt, style, setting)
            log_info(f"Generated prompt for FLUX.1: {full_prompt[:120]}...")

            if persist and not force_refresh:
                existing = self.check_existing_image(prompt_signature)
                if existing:
                    hydrated = self._hydrate_existing_image(
                        existing, full_prompt, style, prompt_signature, setting, prompt
                    )
                    self._set_cache_entry(prompt_signature, hydrated)
                    hydrated['cache_hit'] = True
                    hydrated['source'] = 'database'
                    return hydrated

            image_url = self._generate_with_retry(
                prompt=full_prompt,
                prompt_signature=prompt_signature,
                negative_prompt=self._negative_prompt,
                setting=setting
            )

            if not image_url:
                log_error("Failed to generate image after all retries")
                return {"error": "Image generation failed"}

            # Bootstrap reference image if not already set
            if not self.character_reference_url:
                log_info("Setting character reference from first successful generation")
                self.set_character_reference(image_url)

            result: Dict[str, Any] = {
                'image_url': image_url,
                'style': style,
                'prompt': full_prompt,
                'prompt_signature': prompt_signature,
                'setting': setting,
                'model': self._flux_model
            }

            if persist:
                filename = f"influencer_{uuid.uuid4().hex[:8]}_{style}.png"
                storage_path = self.download_and_upload(image_url, filename)

                if not storage_path:
                    log_error("Failed to upload image to storage")
                    return {"error": "Image upload failed"}

                image_id = str(uuid.uuid4())
                image_metadata = {
                    'style': style,
                    'setting': setting,
                    'original_prompt': prompt,
                    'full_prompt': full_prompt,
                    'prompt_hash': prompt_signature,
                    'model': self._flux_model,
                    'generated_at': datetime.now(self.sa_tz).isoformat(),
                    'character_reference_url': self.character_reference_url,
                }

                image_data = {
                    'image_url': image_url,
                    'storage_path': storage_path,
                    'image_type': 'influencer_photo',
                    'file_size': 0,
                    'dimensions': {'width': 1024, 'height': 1024},
                    'alt_text': f"AI generated influencer image: {prompt}",
                    'metadata': image_metadata
                }

                db_image_id = self.db.save_image(image_data)

                result.update({
                    'storage_path': storage_path,
                    'image_id': image_id,
                    'db_image_id': db_image_id,
                })

            self._set_cache_entry(prompt_signature, result)
            log_info(f"Successfully generated image for signature {prompt_signature[:8]}...")
            return result

        except Exception as e:
            log_error(f"Error generating influencer image: {str(e)}")
            return {"error": str(e)}
    
    def download_and_upload(self, replicate_url: str, filename: str) -> str:
        """Download image from Replicate and upload to Supabase Storage
        
        Args:
            replicate_url: URL of the generated image from Replicate
            filename: Desired filename for the stored image
            
        Returns:
            str: Storage path if successful, empty string if failed
        """
        try:
            log_info(f"Downloading image from: {replicate_url}")
            
            # Download image
            response = requests.get(replicate_url, timeout=30)
            response.raise_for_status()
            
            # Upload to Supabase Storage
            storage_path = f"social-media-images/{filename}"
            
            # Upload to Supabase Storage bucket
            upload_result = self.db.db.storage.from_('social-media-images').upload(
                storage_path, 
                response.content,
                file_options={"content-type": "image/png"}
            )
            
            if upload_result:
                log_info(f"Image uploaded successfully to: {storage_path}")
                return storage_path
            else:
                log_error("Failed to upload image to Supabase Storage")
                return ""
                
        except Exception as e:
            log_error(f"Error downloading/uploading image: {str(e)}")
            return ""

    def set_character_reference(self, reference_image: str) -> bool:
        """Set a reference image to guide character consistency.

        Args:
            reference_image: URL or local path to the reference image.

        Returns:
            bool: True if the reference image was set successfully.
        """
        try:
            if not reference_image:
                raise ValueError("Reference image path or URL is required")

            if self._is_remote_reference(reference_image):
                if not self._validate_reference_url(reference_image):
                    raise ValueError("Reference image URL is not accessible")

            image_bytes = self._resolve_image_bytes(reference_image)
            self.character_reference_url = reference_image
            self._character_reference_bytes = image_bytes

            log_info("Character reference updated successfully")
            return True

        except Exception as e:
            log_error(f"Failed to set character reference: {str(e)}")
            return False

    def generate_consistent_character(
        self,
        prompt: str,
        style: str = "professional",
        setting: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict:
        """Generate a character-aligned image without persisting it to storage."""
        return self._generate_character_image(
            prompt=prompt,
            style=style,
            setting=setting,
            persist=False,
            use_cache=not force_refresh,
            force_refresh=force_refresh
        )

    def validate_character_consistency(self, image1: Any, image2: Any) -> Tuple[bool, float]:
        """Validate whether two images depict the same character profile.

        Returns:
            Tuple[bool, float]: (is_consistent, distance_score)
        """
        try:
            bytes_1 = self._resolve_image_bytes(image1)
            bytes_2 = self._resolve_image_bytes(image2)

            with Image.open(BytesIO(bytes_1)) as img1, Image.open(BytesIO(bytes_2)) as img2:
                img1 = img1.convert('RGB').resize((256, 256))
                img2 = img2.convert('RGB').resize((256, 256))

                diff = ImageChops.difference(img1, img2)
                stat = ImageStat.Stat(diff)
                rms = sum(stat.rms) / len(stat.rms)

                is_consistent = rms <= self._consistency_threshold
                log_info(
                    f"Character consistency validation score: {rms:.2f} (threshold: {self._consistency_threshold})"
                )
                return is_consistent, rms

        except Exception as e:
            log_error(f"Failed to validate character consistency: {str(e)}")
            return False, float('inf')

    def _get_prompt_signature(self, context: str, style: str, setting: str) -> str:
        seed_source = f"{context.strip().lower()}|{style.lower()}|{setting.lower()}|{self._character_profile['name']}"
        return hashlib.sha256(seed_source.encode('utf-8')).hexdigest()

    def _deterministic_seed(self, prompt_signature: str) -> int:
        return int(prompt_signature[:16], 16) % (2**31)

    def _get_cached_image(self, prompt_signature: str) -> Optional[Dict[str, Any]]:
        cached = self._prompt_cache.get(prompt_signature)
        if not cached:
            return None

        if (time.time() - cached['timestamp']) > self._cache_ttl_seconds:
            log_info(f"Cache entry expired for signature {prompt_signature[:8]}... removing")
            self._prompt_cache.pop(prompt_signature, None)
            return None

        return dict(cached['payload'])

    def _set_cache_entry(self, prompt_signature: str, payload: Dict[str, Any]) -> None:
        self._prompt_cache[prompt_signature] = {
            'timestamp': time.time(),
            'payload': dict(payload)
        }

    def _hydrate_existing_image(
        self,
        existing: Dict[str, Any],
        full_prompt: str,
        style: str,
        prompt_signature: str,
        setting: str,
        original_prompt: str
    ) -> Dict[str, Any]:
        metadata = existing.get('metadata') or {}
        image_url = existing.get('image_url') or metadata.get('image_url')
        storage_path = existing.get('storage_path') or metadata.get('storage_path')

        hydrated = {
            'image_url': image_url,
            'storage_path': storage_path,
            'image_id': existing.get('id') or metadata.get('image_id'),
            'db_image_id': existing.get('id'),
            'style': metadata.get('style', style),
            'prompt': full_prompt,
            'prompt_signature': prompt_signature,
            'setting': metadata.get('setting', setting),
            'model': metadata.get('model', self._flux_model),
            'original_prompt': original_prompt,
        }

        return hydrated

    def _download_image_bytes(self, url: str) -> bytes:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content

    def _resolve_image_bytes(self, image_source: Any) -> bytes:
        if isinstance(image_source, bytes):
            return image_source

        if isinstance(image_source, dict):
            if 'image_url' in image_source:
                return self._download_image_bytes(image_source['image_url'])
            if 'storage_path' in image_source:
                return self._resolve_image_bytes(image_source['storage_path'])

        if isinstance(image_source, str):
            if image_source.startswith('http://') or image_source.startswith('https://'):
                return self._download_image_bytes(image_source)
            if os.path.isfile(image_source):
                with open(image_source, 'rb') as file:
                    return file.read()

        raise ValueError("Unsupported image source for consistency validation")

    @staticmethod
    def _is_remote_reference(reference: Any) -> bool:
        return isinstance(reference, str) and reference.startswith(('http://', 'https://'))

    def _validate_reference_url(self, url: str) -> bool:
        response = None
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            if response.status_code >= 400 or response.status_code == 405:
                response.close()
                response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            log_warning(f"Reference image URL validation failed: {exc}")
            return False
        finally:
            if response is not None:
                response.close()

    def _generate_with_retry(
        self,
        prompt: str,
        prompt_signature: str,
        negative_prompt: Optional[str] = None,
        setting: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        seed = self._deterministic_seed(prompt_signature)
        model_identifier = self._flux_model if not self._flux_version else f"{self._flux_model}:{self._flux_version}"

        for attempt in range(max_retries):
            try:
                log_info(f"Generating image with FLUX.1 (attempt {attempt + 1}/{max_retries})")

                input_payload = {
                    "prompt": prompt,
                    "num_inference_steps": self.config.get('image_generation', {}).get('num_inference_steps', 30),
                    "guidance_scale": self.config.get('image_generation', {}).get('guidance_scale', 3.5),
                    "output_format": "png",
                    "aspect_ratio": self.config.get('image_generation', {}).get('aspect_ratio', '1:1'),
                    "seed": seed + attempt,
                }

                if negative_prompt:
                    input_payload["negative_prompt"] = negative_prompt

                if setting:
                    input_payload["metadata"] = {"setting": setting}

                if self.character_reference_url or self._character_reference_bytes:
                    reference_image = BytesIO(self._character_reference_bytes) if self._character_reference_bytes else self.character_reference_url

                    if reference_image:
                        input_payload.update({
                            "image": reference_image,
                            "mode": "img2img",
                            "strength": self._img2img_strength,
                        })

                output = self.client.run(model_identifier, input=input_payload)

                image_url: Optional[str] = None
                if isinstance(output, list) and output:
                    image_url = output[0]
                elif isinstance(output, dict):
                    image_url = output.get('image') or output.get('output', [None])[0]

                if image_url:
                    log_info(f"Image generated successfully via FLUX.1: {image_url}")
                    return image_url

                log_warning(f"Empty output from FLUX.1 (attempt {attempt + 1})")

            except Exception as e:
                log_error(f"Error generating image with FLUX.1 (attempt {attempt + 1}): {str(e)}")

                if attempt < max_retries - 1:
                    log_info("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    log_error("All retry attempts with FLUX.1 failed")

        return None
    
    def generate_batch(self, prompts: List[Dict[str, Any]], enforce_consistency: bool = True) -> List[Dict]:
        """Generate multiple images with optional consistency validation.

        Args:
            prompts: List of prompt dictionaries with 'prompt', 'style', and optional 'setting'.
            enforce_consistency: Whether to validate consistent character appearance across the batch.

        Returns:
            List[Dict]: List of image data for each generated image.
        """
        try:
            if not isinstance(prompts, list):
                raise ValueError("prompts must be a list of prompt dictionaries")

            log_info(f"Generating batch of {len(prompts)} images")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(self._generate_batch_async(prompts))
            finally:
                loop.close()

            if enforce_consistency:
                results = self._apply_consistency_checks(prompts, results)

            return results

        except Exception as e:
            log_error(f"Error generating batch: {str(e)}")
            return []

    async def _generate_batch_async(self, prompts: List[Dict[str, Any]]) -> List[Dict]:
        """Async implementation of batch generation
        
        Args:
            prompts: List of prompt dictionaries
            
        Returns:
            List[Dict]: List of generated image data
        """
        try:
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests
            
            async def generate_single(prompt_data):
                async with semaphore:
                    prompt_text = prompt_data.get('prompt', '')
                    style = prompt_data.get('style', 'professional')
                    setting = prompt_data.get('setting')

                    if prompt_data.get('persist', True):
                        return self.generate_influencer_image(
                            prompt=prompt_text,
                            style=style,
                            setting=setting,
                            use_cache=prompt_data.get('use_cache', True)
                        )

                    return self.generate_consistent_character(
                        prompt=prompt_text,
                        style=style,
                        setting=setting,
                        force_refresh=prompt_data.get('force_refresh', False)
                    )
            
            # Generate all images concurrently
            tasks = [generate_single(prompt) for prompt in prompts]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            normalized_results: List[Dict] = []
            success_count = 0

            for item in results:
                if isinstance(item, Exception):
                    log_error(f"Batch generation task failed: {str(item)}")
                    normalized_results.append({'error': str(item)})
                elif isinstance(item, dict):
                    normalized_results.append(item)
                    if 'error' not in item:
                        success_count += 1
                else:
                    normalized_results.append({'error': 'Unknown response from image generator'})

            log_info(f"Batch generation completed: {success_count}/{len(prompts)} successful")
            return normalized_results
            
        except Exception as e:
            log_error(f"Error in async batch generation: {str(e)}")
            return []
    
    def _apply_consistency_checks(self, prompts: List[Dict[str, Any]], results: List[Dict]) -> List[Dict]:
        if not results:
            return results

        reference_url = self.character_reference_url
        first_valid_image = next((r.get('image_url') for r in results if isinstance(r, dict) and r.get('image_url')), None)

        if not reference_url and first_valid_image:
            self.set_character_reference(first_valid_image)
            reference_url = first_valid_image

        validated_results: List[Dict] = []
        for idx, result in enumerate(results):
            if not isinstance(result, dict):
                continue

            image_url = result.get('image_url')
            if not image_url:
                validated_results.append(result)
                continue

            baseline_url = reference_url or image_url
            is_consistent, score = (True, 0.0) if image_url == baseline_url else self.validate_character_consistency(baseline_url, image_url)

            result['is_consistent'] = is_consistent
            result['consistency_score'] = score

            if not is_consistent:
                log_warning(f"Inconsistency detected for batch item {idx}. Attempting regeneration with reference guidance.")
                prompt_payload = prompts[idx] if idx < len(prompts) else {}
                retry = self._generate_character_image(
                    prompt=prompt_payload.get('prompt', result.get('prompt', '')),
                    style=prompt_payload.get('style', result.get('style', 'professional')),
                    setting=prompt_payload.get('setting', result.get('setting')),
                    persist=prompt_payload.get('persist', True),
                    use_cache=False,
                    force_refresh=True
                )

                if isinstance(retry, dict) and retry.get('image_url'):
                    baseline_for_retry = reference_url or retry['image_url']
                    retry_consistent, retry_score = self.validate_character_consistency(baseline_for_retry, retry['image_url'])
                    retry['is_consistent'] = retry_consistent
                    retry['consistency_score'] = retry_score

                    if retry_consistent:
                        result = retry
                    else:
                        warnings = result.setdefault('warnings', [])
                        warnings.append('consistency_check_failed')
                        result['retry_result'] = retry
                else:
                    warnings = result.setdefault('warnings', [])
                    warnings.append('consistency_regeneration_failed')

            if reference_url is None and image_url:
                self.set_character_reference(image_url)
                reference_url = image_url

            validated_results.append(result)

        return validated_results

    def add_lora_to_prompt(self, prompt: str, lora_trigger: str) -> str:
        """Add Lora trigger words to prompt
        
        Args:
            prompt: Base prompt
            lora_trigger: Lora trigger words (currently placeholder)
            
        Returns:
            str: Prompt with Lora trigger words added
        """
        # PLACEHOLDER: For when Lora file arrives
        # Currently returns prompt unchanged
        if lora_trigger:
            return f"{lora_trigger}, {prompt}"
        return prompt
    
    def check_existing_image(self, prompt_hash: str) -> Optional[Dict]:
        """Check if a similar image already exists to avoid regeneration
        
        Args:
            prompt_hash: Hash of the prompt to check for
            
        Returns:
            Optional[Dict]: Existing image data if found, None otherwise
        """
        try:
            # Query database for existing images with similar prompt hash
            result = self.db.db.table('social_images').select('*').eq(
                'metadata->>prompt_hash', prompt_hash
            ).execute()
            
            if result.data:
                log_info(f"Found existing image for prompt hash: {prompt_hash}")
                return result.data[0]
            
            return None
            
        except Exception as e:
            log_error(f"Error checking existing image: {str(e)}")
            return None
    
    def get_generation_stats(self) -> Dict:
        """Get statistics about image generation
        
        Returns:
            Dict: Statistics about generated images
        """
        try:
            # Get total images generated
            total_result = self.db.db.table('social_images').select('id', count='exact').execute()
            total_images = total_result.count if total_result.count else 0
            
            # Get images by style
            style_result = self.db.db.table('social_images').select(
                'metadata->>style'
            ).execute()
            
            style_counts = {}
            if style_result.data:
                for item in style_result.data:
                    style = item.get('metadata', {}).get('style', 'unknown')
                    style_counts[style] = style_counts.get(style, 0) + 1
            
            # Get recent generation activity (last 7 days)
            from datetime import timedelta
            week_ago = datetime.now(self.sa_tz) - timedelta(days=7)
            
            recent_result = self.db.db.table('social_images').select('id', count='exact').gte(
                'created_at', week_ago.isoformat()
            ).execute()
            recent_images = recent_result.count if recent_result.count else 0
            
            stats = {
                'total_images': total_images,
                'recent_images': recent_images,
                'style_distribution': style_counts,
                'last_updated': datetime.now(self.sa_tz).isoformat()
            }
            
            log_info(f"Retrieved generation stats: {stats}")
            return stats
            
        except Exception as e:
            log_error(f"Error getting generation stats: {str(e)}")
            return {
                'total_images': 0,
                'recent_images': 0,
                'style_distribution': {},
                'error': str(e)
            }
