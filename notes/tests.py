import uuid
from django.test import TestCase
from your_app.utils import build_attachment_key, ATTACHMENT_ID_RE

class AttachmentKeyTests(TestCase):
    def test_regex_stays_in_sync_with_builder(self):
        """
        Ensures that if the URL structure of build_attachment_key changes, 
        the ATTACHMENT_ID_RE regex is updated to successfully extract the UUID.
        """
        test_uuid = str(uuid.uuid4())
        
        # 1. Generate the key using your function
        generated_key = build_attachment_key(
            user_id="user_123",
            note_id="note_456",
            attachment_id=test_uuid,
            filename="my_cool_screenshot.png"
        )
        
        # 2. Simulate how it looks inside markdown (with domain and leading slash)
        markdown_url = f"https://my-bucket.r2.cloudflarestorage.com/{generated_key}"
        
        # 3. Extract it using your regex
        matches = ATTACHMENT_ID_RE.findall(markdown_url)
        
        # 4. Assert they perfectly match
        self.assertEqual(len(matches), 1, "Regex failed to find the UUID in the generated key.")
        self.assertEqual(matches[0], test_uuid, "Regex extracted the wrong UUID.")