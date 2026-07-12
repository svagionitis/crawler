class BaseContentProcessor:
    """Strategy interface for processing crawled pages."""

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        """
        Process page content, perform custom parsing/extraction, save payload data,
        and extract links for further crawling.

        Args:
            crawler: The crawler instance (for configuration/DB access).
            url (str): The fetched URL.
            content (str): The raw page content.
            content_type (str): The MIME type.

        Returns:
            tuple: (success_status, extracted_links, action_flag)
        """
        raise NotImplementedError
