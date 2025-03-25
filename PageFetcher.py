import requests
import time
import logging
import base64

class PageFetcher:
    def __init__(self, user_agent):
        self.user_agent = user_agent

    def fetch_page(self, url, max_retries=3, initial_timeout=60):
        """
        Fetch the content of a web page with retries and exponential backoff.

        Args:
            url (str): The URL to fetch.
            max_retries (int): Maximum number of retries (default: 3).
            initial_timeout (int): Initial timeout in seconds (default: 60).

        Returns:
            tuple: (content, error_description) where content is the page content or None,
                and error_description is an error message or None.
        """
        headers = {"User-Agent": self.user_agent}
        retry_count = 0
        timeout = initial_timeout

        while retry_count < max_retries:
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()

                # Check the Content-Type header
                content_type = response.headers.get("Content-Type", "").lower()

                if "text/" in content_type:
                    # Return text content as plain text
                    return response.text, None
                else:
                    # Return binary content as Base64-encoded string
                    return base64.b64encode(response.content).decode("utf-8"), None

            except requests.exceptions.HTTPError as e:
                if response.status_code == 504:  # Handle 504 Gateway Timeout
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.warning(f"504 Gateway Timeout for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                        time.sleep(timeout)  # Wait before retrying
                        timeout *= 2  # Exponential backoff
                    else:
                        error_description = f"504 Gateway Timeout after {max_retries} retries: {e}"
                        logging.error(f"Failed to fetch {url}: {error_description}")
                        return None, error_description
                else:
                    error_description = f"HTTP Error {response.status_code}: {e}"
                    logging.error(f"Failed to fetch {url}: {error_description}")
                    return None, error_description

            except requests.exceptions.Timeout as e:
                retry_count += 1
                if retry_count < max_retries:
                    logging.warning(f"Timeout occurred for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(timeout)  # Wait before retrying
                    timeout *= 2  # Exponential backoff
                else:
                    error_description = f"Timeout after {max_retries} retries: {e}"
                    logging.error(f"Failed to fetch {url}: {error_description}")
                    return None, error_description

            except requests.exceptions.RequestException as e:
                error_description = str(e)
                logging.error(f"Failed to fetch {url}: {error_description}")
                return None, error_description

        return None, "Max retries reached without success"
