class PropertyScraper:
    def __init__(self, transaction_type="rent"):
        """Initialise WebDriver with transaction type (rent or buy)"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.binary_location = "/usr/bin/chromium"
            self.service = Service("/usr/bin/chromedriver")
            self.driver = webdriver.Chrome(service=self.service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            
            # Set URL based on transaction type
            self.transaction_type = transaction_type
            if transaction_type == "rent":
                self.url = "https://www.squarefoot.com.hk/en/rent"
                self.price_field = "Monthly Rental Price (in HKD)"
                self.price_css_selector = 'span.priceDesc.rentDesc'
            else:  # buy
                self.url = "https://www.squarefoot.com.hk/en/buy"
                self.price_field = "Sale Price (in HKD)"
                self.price_css_selector = 'span.priceDesc'  # Remove the space, just use the class name
            
            self.driver.get(self.url)
            time.sleep(2)  # Give page time to load
        except Exception as e:
            st.error(f"Error setting up WebDriver: {e}")
            raise

    def extract_price_from_text(self, price_text):
        """
        Extract numeric price from text like "Sell HKD$12.8 Millions" or "Lease HKD$50,000"
        Returns the price as a string with commas removed.
        """
        if not price_text or price_text == 'N/A':
            return 'N/A'
        
        try:
            if self.transaction_type == "rent":
                # For rent: "Lease HKD$50,000" -> remove prefix and commas
                cleaned = price_text.replace('Lease HKD$', '').replace('Lease', '').replace('HKD$', '').replace(',', '').strip()
                return cleaned if cleaned else 'N/A'
            else:
                # For buy: "Sell HKD$12.8 Millions" -> extract number and convert
                # Remove "Sell HKD$" prefix and any other text
                cleaned = price_text.replace('Sell HKD$', '').replace('Sell', '').replace('HKD$', '').strip()
                
                # Check if it's in "Millions" format
                if 'Million' in cleaned:
                    # Extract the number before "Million(s)"
                    import re
                    number_match = re.search(r'([\d.]+)', cleaned)
                    if number_match:
                        number_part = number_match.group(1)
                        try:
                            # Convert to float and multiply by 1,000,000
                            price_value = float(number_part) * 1_000_000
                            # Return as integer string without commas
                            return str(int(price_value))
                        except ValueError:
                            pass
                
                # If not in millions format or conversion failed, try direct number extraction
                import re
                # Extract just the number (including decimals and commas)
                numbers = re.findall(r'[\d,]+\.?\d*', cleaned)
                if numbers:
                    # Remove commas and return
                    return numbers[0].replace(',', '')
                
                return 'N/A'
        except Exception as e:
            return 'N/A'
    
    def get_total_pages(self):
        """
        Get the total number of pages from pagination.
        Returns the maximum page number or 1 if no pagination found.
        """
        try:
            time.sleep(2)
            
            # Find pagination container
            pagination_container = self.driver.find_elements(By.CSS_SELECTOR, 'div.ui.borderless.menu.pagination')
            
            if not pagination_container:
                return 1
            
            # Find all page number items with attr1 attribute
            page_items = pagination_container[0].find_elements(By.CSS_SELECTOR, 'a.item[attr1]')
            
            # Extract page numbers from attr1 values
            page_numbers = []
            for item in page_items:
                attr_value = item.get_attribute('attr1')
                if attr_value:
                    try:
                        # Try to convert to integer
                        page_num = int(attr_value)
                        page_numbers.append(page_num)
                    except ValueError:
                        # If it's not a valid integer, skip it
                        continue
            
            if page_numbers:
                total_pages = max(page_numbers)
                return total_pages
            
            return 1
                    
        except Exception as e:
            st.error(f"Error getting total pages: {e}")
            return 1
    
    def go_to_next_page(self):
        """
        Click the next page button.
        Returns True if successful, False if no next page exists.
        """
        try:
            time.sleep(1)
            
            # Find the next page button with attr1="plus"
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a.item[attr1="plus"]')
            
            if not next_buttons:
                return False
            
            next_button = next_buttons[0]
            next_button.click()
            time.sleep(3)
            
            # Wait for properties to load
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
            
            return True
            
        except Exception as e:
            st.error(f"Error going to next page: {e}")
            return False
    
    def get_current_page_number(self):
        """
        Get the current page number.
        """
        try:
            # Find active page item
            active_items = self.driver.find_elements(By.CSS_SELECTOR, 'a.item.active')
            
            for item in active_items:
                text = item.text.strip()
                if text:
                    try:
                        # Try to convert to integer
                        return int(text)
                    except ValueError:
                        continue
            
            return 1
        except:
            return 1
    
    def extract_all_property_data(self, district, total_properties):
        """
        Extract data from all property listings across all pages.
        
        Args:
            district: The district to scrape
            total_properties: Total number of properties found (from search results)
        """
        all_properties_data = []
        current_page = 1
    
        try:
            total_pages = self.get_total_pages()
            
            # Show total properties instead of pages
            st.info(f"Total properties to scrape: {total_properties:,}")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            properties_scraped = 0
            
            while current_page <= total_pages:
                # Extract properties from current page
                page_properties = self.extract_property_data(district)
                all_properties_data.extend(page_properties)
                properties_scraped += len(page_properties)
                
                # Update status with current count
                status_text.text(f"Scraping properties... {properties_scraped:,} of {total_properties:,} properties scraped")
                
                # Update progress based on total properties
                if total_properties > 0:
                    progress = properties_scraped / total_properties
                    progress_bar.progress(progress)
                
                if current_page >= total_pages:
                    break
                
                if not self.go_to_next_page():
                    st.warning(f"Could not go to page {current_page + 1}")
                    break
                
                current_page += 1
            
            # Final update
            progress_bar.empty()
            status_text.empty()
            
            # Show final count
            st.success(f"Successfully scraped {properties_scraped:,} of {total_properties:,} properties")
            
        except Exception as e:
            st.error(f"Error during extraction: {e}")
        
        return all_properties_data

    def apply_generic_filter(self, filter_attr, choice, mapping, filter_name):
        """
        Generic helper method to apply any filter on the website.
        
        Args:
            filter_attr: The 'attr' attribute value (e.g., "mainType", "price", "areaRange")
            choice: The user's choice (string like "1", "2", "3", etc.)
            mapping: Dictionary mapping user choice to website data-value
            filter_name: Name of the filter for logging (e.g., "property type", "budget")
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if choice not in mapping:
                st.error(f"Invalid {filter_name} choice: {choice}")
                return False
            
            data_value = mapping[choice]
            
            filter_container = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'div[attr="{filter_attr}"]')))
            
            options = filter_container.find_elements(By.CSS_SELECTOR, '.ui.groupTop.horizontal.list.level0 a.item')
            
            for option in options:
                option_data_value = option.get_attribute('data-value')
                if option_data_value == data_value:
                    option.click()
                    time.sleep(1)
                    return True
            
            st.error(f"Option with data-value '{data_value}' not found for {filter_name}")
            return False
            
        except Exception as e:
            st.error(f"Error applying {filter_name.title()} filter: {e}")
            return False

    def apply_property_type_filter(self, property_type):
        """Apply property type filter on website."""
        type_mapping = {
            "All": "0",
            "Apartment": "5",
            "Carpark": "6", 
            "Office": "7",
            "Shop": "8"
        }
        
        return self.apply_generic_filter("mainType", property_type, type_mapping, "Property Type")

    def apply_budget_filter(self, budget_choice):
        """Apply budget filter based on transaction type."""
        if self.transaction_type == "rent":
            budget_mapping = {
                "No preference": "0", 
                "Below 10,000": "1", 
                "10,000 - 20,000": "2", 
                "20,000 - 40,000": "3", 
                "40,000 - 60,000": "4", 
                "60,000 - 80,000": "5", 
                "Above 80,000": "6"
            }
        else:  # buy
            budget_mapping = {
                "No preference": "0",
                "Below 10M": "1",
                "10M - 20M": "2",
                "20M - 40M": "3",
                "40M - 70M": "4",
                "70M - 100M": "5",
                "Above 100M": "6"
            }
        
        return self.apply_generic_filter("price", budget_choice, budget_mapping, 
                                        "Budget" if self.transaction_type == "rent" else "Price")

    def apply_area_filter(self, area_choice):
        """Apply area filter on website."""
        area_mapping = {
            "No preference": "0", 
            "Below 300": "1", 
            "300 - 500": "2", 
            "500 - 1000": "3", 
            "1000 - 2000": "4", 
            "Above 2000": "5"
        }
        
        return self.apply_generic_filter("areaRange", area_choice, area_mapping, "Saleable Area")
        
    def apply_room_filter(self, room_choice):
        """Apply room filter on website."""
        room_mapping = {
            "No preference": "0",
            "Studio": "STUDIO",
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "5+": "5PLUS"
        }
        
        return self.apply_generic_filter("roomRange", room_choice, room_mapping, "Number of Rooms")
    
    def search_district(self, district):
        """Search for properties in the specified district."""
        try:
            search_input = self.wait.until(EC.element_to_be_clickable((By.NAME, 'searchText_temp')))
            search_input.clear()
            time.sleep(0.5)
            search_input.send_keys(district)
            
            search_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'searchwords_btn')))
            search_button.click()
            time.sleep(3)
            
            # Get the results count directly
            results_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[style*="float: left"]')))
            results_text = results_element.text.strip()
            
            # Check for appropriate result text based on transaction type
            if self.transaction_type == "rent":
                if "results of property for lease" in results_text:
                    num_str = results_text.split()[0].replace(',', '')
                    try:
                        property_count = int(num_str)
                        return property_count
                    except ValueError:
                        return 0
            else:  # buy
                if "results of property for sale" in results_text:
                    num_str = results_text.split()[0].replace(',', '')
                    try:
                        property_count = int(num_str)
                        return property_count
                    except ValueError:
                        return 0
            return 0
            
        except Exception as e:
            st.error(f"Error searching district '{district}': {e}")
            return 0
    
    def extract_property_name(self, header_element, district):
        """
        Extract property name from header.cat element
        """
        try:
            # Get text and split by newline
            full_text = header_element.text.strip()
            lines = full_text.split('\n')
            
            if lines:
                first_line = lines[0].strip()
                
                # Remove district if it's at the beginning
                if first_line.startswith(district):
                    property_name = first_line[len(district):].strip()
                else:
                    property_name = first_line
                
                return property_name
            else:
                return 'N/A'
                
        except Exception as e:
            return 'N/A'
    
    def extract_property_data(self, district):
        """
        Extract data from all property listings on the current page.
        """
        properties_data = []
        
        try:
            # Wait for property listings to load
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
            time.sleep(2)
            
            # Find all property listings
            property_items = self.driver.find_elements(By.CSS_SELECTOR, 'div.item.property_item')
            
            for item in property_items:
                property_data = {}
                
                try:
                    # 1. DISTRICT - Use the user's search input
                    property_data['District'] = district
                    
                    # 2. NAME - Extract property name
                    try:
                        header_cat = item.find_element(By.CSS_SELECTOR, 'div.header.cat')
                        property_data['Name'] = self.extract_property_name(header_cat, district)
                    except:
                        property_data['Name'] = 'N/A'
                    
                    # 3. STREET ADDRESS - Extract property address
                    try:
                        # Find all div.meta elements in this property item
                        meta_divs = item.find_elements(By.CSS_SELECTOR, 'div.meta')
                        if meta_divs:
                            # The first meta div contains the street address
                            property_data['Street Address'] = meta_divs[0].text.strip()
                        else:
                            property_data['Street Address'] = 'N/A'
                    except:
                        property_data['Street Address'] = 'N/A'
                    
                    # 4. PRICE - Extract property price using the price_css_selector and extract_price_from_text
                    try:
                        # Find price element using the class selector
                        price_element = item.find_element(By.CSS_SELECTOR, self.price_css_selector)
                        price_text = price_element.text.strip()
                        # Use the extract_price_from_text method to handle both rent and buy formats
                        property_data[self.price_field] = self.extract_price_from_text(price_text)
                    except Exception as e:
                        # If the primary selector fails, try alternative selectors
                        try:
                            # Try with a more generic approach
                            price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc')
                            price_text = price_element.text.strip()
                            property_data[self.price_field] = self.extract_price_from_text(price_text)
                        except:
                            property_data[self.price_field] = 'N/A'
        
                    # 5, 6, 7. Extract Net Area, Bedrooms, and Bathrooms
                    try:
                        # Find the header with ft²
                        header_divs = item.find_elements(By.CSS_SELECTOR, 'div.header')
                        
                        for header in header_divs:
                            text = header.text.strip()
                            
                            if 'ft²' in text:
                                # Split the text by whitespace
                                parts = text.split()
                                # 1. Net Area (first number before ft²)
                                if len(parts) > 0:
                                    property_data['Net Area (sqft)'] = parts[0]
                                
                                # 2. Bedrooms (third element, index 2)
                                if len(parts) > 2:
                                    property_data['Number of Bedrooms'] = parts[2]
                                
                                # 3. Bathrooms (fourth element, index 3)
                                if len(parts) > 3:
                                    property_data['Number of Bathrooms'] = parts[3]
                                
                                break
                        
                        # Set defaults if not found
                        if 'Net Area (sqft)' not in property_data:
                            property_data['Net Area (sqft)'] = 'N/A'
                        if 'Number of Bedrooms' not in property_data:
                            property_data['Number of Bedrooms'] = 'N/A'
                        if 'Number of Bathrooms' not in property_data:
                            property_data['Number of Bathrooms'] = 'N/A'     
                    except:
                        property_data['Net Area (sqft)'] = 'N/A'
                        property_data['Number of Bedrooms'] = 'N/A'
                        property_data['Number of Bathrooms'] = 'N/A'
                    
                    # 8. URL - Extract from img.detail_page href attribute
                    try:
                        # Find the image element
                        img_element = item.find_element(By.CSS_SELECTOR, 'img.desktop_myimage.detail_page')
                        # Get the href attribute which contains the URL
                        property_data['URL'] = img_element.get_attribute('href')
                    except:
                        property_data['URL'] = 'N/A'
                    
                    # Add to list
                    properties_data.append(property_data)
                    
                except Exception as e:
                    # If we can't extract data from this property, skip it
                    continue
            
        except Exception as e:
            st.error(f"Error extracting property data: {e}")
        
        return properties_data
    
    def save_to_csv(self, properties_data):
        """
        Save extracted property data to a CSV string and return as bytes.
        """
        if not properties_data:
            return None
        
        try:
            # Define headers dynamically based on transaction type
            if self.transaction_type == "rent":
                headers = [
                    "District", "Name", "Street Address", "Monthly Rental Price (in HKD)", 
                    "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"
                ]
            else:  # buy
                headers = [
                    "District", "Name", "Street Address", "Sale Price (in HKD)", 
                    "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"
                ]
            
            # Create a string buffer to write CSV data
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for property_data in properties_data:
                writer.writerow(property_data)
            
            # Get the CSV string and encode to bytes
            csv_string = output.getvalue()
            output.close()
            
            return csv_string.encode('utf-8')
            
        except Exception as e:
            st.error(f"Error saving to CSV: {e}")
            return None
    
    def close(self):
        """Close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()
