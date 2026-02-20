import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import csv
import os
import pandas as pd
from tempfile import NamedTemporaryFile
import io

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
                self.price_text_pattern = "Lease HKD$"
            else:  # buy
                self.url = "https://www.squarefoot.com.hk/en/buy"
                self.price_field = "Sale Price (in HKD)"
                self.price_css_selector = 'span.priceDesc '  # More generic selector for sale price
                # No pattern needed as we'll extract using regex
            
            self.driver.get(self.url)
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
                return price_text.replace('Lease HKD$', '').replace(',', '').strip()
            else:
                # For buy: "Sell HKD$12.8 Millions" -> extract number and convert
                # Remove "Sell HKD$" prefix
                price_text = price_text.replace('Sell HKD$', '').strip()
                
                # Check if it's in "Millions" format
                if 'Millions' in price_text:
                    # Extract the number before "Millions"
                    number_part = price_text.replace('Millions', '').strip()
                    try:
                        # Convert to float and multiply by 1,000,000
                        price_value = float(number_part) * 1_000_000
                        # Return as integer string without commas
                        return str(int(price_value))
                    except ValueError:
                        pass
                
                # If not in millions format or conversion failed, try direct number
                # Remove any remaining text and commas
                import re
                # Extract just the number (including decimals)
                numbers = re.findall(r'[\d,]+\.?\d*', price_text)
                if numbers:
                    # Remove commas and return
                    return numbers[0].replace(',', '')
                
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
                    
                    # 4. PRICE - Extract property price based on transaction type
                    try:
                        # Find price element - different selectors for rent vs buy
                        if self.transaction_type == "rent":
                            price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc.rentDesc')
                        else:
                            # For buy, find the span with priceDesc class
                            price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc ')
                        
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
                    
                    # 4. PRICE - Extract property price based on transaction type
                    try:
                        price_element = item.find_element(By.CSS_SELECTOR, self.price_css_selector)
                        price_text = price_element.text.strip()
                        # Remove the prefix and keep just the number
                        property_data[self.price_field] = price_text.replace(self.price_text_pattern, '').strip()   
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

def show_home_page():
    """Display the home page with instructions"""
    st.markdown("""
    #### Welcome to the *Hong Kong Property Scraper!*
    
    This tool helps you search and extract property data in Hong Kong for both **rental** and **sale** properties *(data retrieved from SquareFoot.com.hk)*. 
    Get started by navigating to the **Property Search** tab above.
    
    ---
    
    ### Quick Start Guide
    
    #### Step 1: Navigate to Property Search
    Click on the **"Property Search"** tab at the top of the page.
    
    #### Step 2: Select Transaction Type
    Choose between **Rent** or **Buy** properties.
    
    #### Step 3: Apply Filters (Optional)
    Use the filters in the search form to narrow down your search:
    - **Property Type**: Select from All, Apartment, Carpark, Office, or Shop
    - **Budget/Price Range**: Choose your preferred price range (options change based on transaction type)
    - **Saleable Area**: Filter by property size
    - **Number of Rooms**: Select bedroom requirements
    
    #### Step 4: Enter District
    - Type the Hong Kong district you want to search (e.g., "Central", "Causeway Bay", "Tsim Sha Tsui")
    - Click the **"Search Properties"** button
    
    #### Step 5: Review Search Results
    - The app will show you how many properties were found
    - If no properties match your criteria, try broadening your filters
    
    #### Step 6: Extract Data
    - Click **"Extract Property Data"** to start scraping
    - A progress bar will show real-time progress
    - Extraction time varies based on the number of properties
    
    #### Step 7: Download Your Data
    - Once extraction is complete, you'll see a table with all property details
    - Click the **"Download CSV"** button to save the data
    
    ---
    
    ### What Data Gets Extracted?
    
    For each property, the scraper collects:
    
    1. **District** - Your searched location
    2. **Property Name** - Building/project name
    3. **Street Address** - Full street address
    4. **Price** - Monthly rent (for rentals) or sale price (for purchases) in HKD
    5. **Net Area** - Size in square feet
    6. **Number of Bedrooms**
    7. **Number of Bathrooms**
    8. **Property URL** - Direct link to the listing
    
    ---
    
    ### Tips
    
    - **Start broad**: Begin with fewer filters to see more options
    - **Be specific**: Use exact district names for best results
    - **Be patient**: Large searches (1000+ properties) may take a few minutes
    - **Check spelling**: The search is case-insensitive but needs correct spelling
    
    ---
    
    ### Need Help?
    
    If you encounter any issues:
    - Check your internet connection
    - Verify the district name is correct
    - Try refreshing the page and starting over
    
    ---
    
    *Happy Property Hunting!*
    """)

def show_property_search():
    """Display the property search interface"""
    
    # Initialize session state for this tab
    if 'scraper' not in st.session_state:
        st.session_state.scraper = None
    if 'properties_data' not in st.session_state:
        st.session_state.properties_data = None
    if 'search_performed' not in st.session_state:
        st.session_state.search_performed = False
    if 'extract_clicked' not in st.session_state:
        st.session_state.extract_clicked = False
    if 'current_district' not in st.session_state:
        st.session_state.current_district = ""
    if 'property_count' not in st.session_state:
        st.session_state.property_count = 0
    if 'is_extracting' not in st.session_state:
        st.session_state.is_extracting = False
    if 'transaction_type' not in st.session_state:
        st.session_state.transaction_type = "rent"
    
    # Transaction Type Selection (outside the form so it updates immediately)
    st.subheader("Transaction Type")
    transaction_type = st.radio(
        "Select transaction type:",
        ["Rent", "Buy"],
        horizontal=True,
        key="transaction_type_radio",
        on_change=lambda: setattr(st.session_state, 'search_performed', False)  # Reset search when type changes
    ).lower()
    
    # Update session state with transaction type
    if st.session_state.transaction_type != transaction_type:
        st.session_state.transaction_type = transaction_type
        st.session_state.search_performed = False
        st.session_state.properties_data = None
        st.session_state.extract_clicked = False
    
    # Create a form for search filters
    with st.form("search_form"):
        st.subheader("Search Filters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Property Type Selection
            property_type = st.selectbox(
                "Property Type",
                ["All", "Apartment", "Carpark", "Office", "Shop"],
                key="property_type"
            )
            
            # Budget/Price Selection based on transaction type from session state
            if st.session_state.transaction_type == "rent":
                budget_options = [
                    "No preference", "Below 10,000", "10,000 - 20,000", 
                    "20,000 - 40,000", "40,000 - 60,000", "60,000 - 80,000", 
                    "Above 80,000"
                ]
                budget_label = "Monthly Budget (HKD)"
                budget_help = "Select your preferred monthly rental budget"
            else:  # buy
                budget_options = [
                    "No preference", "Below 10M", "10M - 20M", 
                    "20M - 40M", "40M - 70M", "70M - 100M", 
                    "Above 100M"
                ]
                budget_label = "Price Range (HKD)"
                budget_help = "Select your preferred purchase price range"
            
            budget = st.selectbox(
                budget_label,
                budget_options,
                key="budget",
                help=budget_help
            )
        
        with col2:
            # Area Selection (only if not Carpark)
            if property_type != "Carpark":
                area = st.selectbox(
                    "Saleable Area (sqft)",
                    ["No preference", "Below 300", "300 - 500", "500 - 1000", 
                     "1000 - 2000", "Above 2000"],
                    key="area"
                )
            else:
                area = "No preference"
                st.info("Area filter not applicable for Carpark")
            
            # Room Selection (only if not Carpark)
            if property_type != "Carpark":
                rooms = st.selectbox(
                    "Number of Rooms",
                    ["No preference", "Studio", "1", "2", "3", "4", "5+"],
                    key="rooms"
                )
            else:
                rooms = "No preference"
                st.info("Room filter not applicable for Carpark")
        
        # District Input
        district = st.text_input("District Name", key="district_input", 
                                help="Enter a Hong Kong district (e.g., Central, Causeway Bay, Tsim Sha Tsui)")
        
        # Search Button
        search_button = st.form_submit_button("Search Properties", type="primary", use_container_width=True)
    
    # Main content area (outside the form)
    if search_button and district:
        with st.spinner("Initializing scraper..."):
            # Close existing scraper if any
            if st.session_state.scraper:
                st.session_state.scraper.close()
                st.session_state.scraper = None
            
            try:
                # Initialize scraper with transaction type from session state
                st.session_state.scraper = PropertyScraper(st.session_state.transaction_type)
                
                # Apply filters
                st.session_state.scraper.apply_property_type_filter(property_type)
                st.session_state.scraper.apply_budget_filter(budget)
                
                if property_type != "Carpark":
                    st.session_state.scraper.apply_area_filter(area)
                    st.session_state.scraper.apply_room_filter(rooms)
                
                # Search district
                property_count = st.session_state.scraper.search_district(district)
                st.session_state.property_count = property_count
                st.session_state.current_district = district
                
                if property_count > 0:
                    st.success(f"Found {property_count:,} properties")
                    st.session_state.search_performed = True
                    st.session_state.extract_clicked = False  # Reset extraction flag
                    st.session_state.properties_data = None  # Clear previous data
                else:
                    st.warning("No properties found in this district")
                    st.session_state.search_performed = False
                    
            except Exception as e:
                st.error(f"Error during search: {e}")
                st.session_state.search_performed = False
                if st.session_state.scraper:
                    st.session_state.scraper.close()
                    st.session_state.scraper = None
    
    # Show extract button if search was successful and data not yet extracted
    if (st.session_state.search_performed and 
        not st.session_state.extract_clicked and 
        st.session_state.property_count > 0 and
        not st.session_state.get('is_extracting', False)):
        
        # Create the extract button
        extract_button = st.button("Extract Property Data", key="extract_button", use_container_width=True)
        
        if extract_button:
            # Set extracting flag immediately and rerun to hide button
            st.session_state.is_extracting = True
            st.rerun()
    
    # Handle extraction process
    if st.session_state.get('is_extracting', False):
        with st.spinner("Extracting property data... This may take a few minutes..."):
            if st.session_state.scraper:
                st.session_state.properties_data = st.session_state.scraper.extract_all_property_data(
                    st.session_state.current_district, 
                    st.session_state.property_count
                )
                st.session_state.extract_clicked = True
                st.session_state.is_extracting = False  # Clear extracting flag
                st.rerun()  # Rerun to show results
            else:
                st.error("Scraper connection lost. Please search again.")
                st.session_state.is_extracting = False
                st.rerun()
    
    # Display results
    if st.session_state.get('properties_data') is not None:
        if len(st.session_state.properties_data) > 0:
            st.header("Search Results")
            
            # Convert to DataFrame for display
            df = pd.DataFrame(st.session_state.properties_data)
            
            # Display dataframe
            st.dataframe(df, use_container_width=True)
            
            # Generate CSV for download
            if st.session_state.scraper:
                csv_bytes = st.session_state.scraper.save_to_csv(st.session_state.properties_data)
                
                if csv_bytes:
                    # Create filename with transaction type
                    transaction_prefix = "rental" if st.session_state.transaction_type == "rent" else "sale"
                    filename = f"{transaction_prefix}_property_data_{st.session_state.current_district}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    
                    # Single download button that directly downloads the CSV
                    st.download_button(
                        label="Download CSV",
                        data=csv_bytes,
                        file_name=filename,
                        mime='text/csv',
                        key="download_csv_button",
                        use_container_width=True
                    )
            
            # Display statistics
            st.header("Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Properties", len(st.session_state.properties_data))
            
            # Calculate average price (excluding 'N/A' values)
            prices = []
            price_field = "Monthly Rental Price (in HKD)" if st.session_state.transaction_type == "rent" else "Sale Price (in HKD)"
            
            for p in st.session_state.properties_data:
                price_str = p.get(price_field, 'N/A')
                if price_str != 'N/A':
                    try:
                        # Remove commas and convert to int
                        price = int(price_str.replace(',', ''))
                        prices.append(price)
                    except:
                        pass
            
            with col2:
                if prices:
                    avg_price = sum(prices) // len(prices)
                    # Format price differently for rent vs buy
                    if st.session_state.transaction_type == "rent":
                        st.metric("Average Monthly Rent (HKD)", f"{avg_price:,}")
                    else:
                        # Convert to millions for sale properties
                        if avg_price >= 1_000_000:
                            st.metric("Average Sale Price (HKD)", f"{avg_price/1_000_000:.1f}M")
                        else:
                            st.metric("Average Sale Price (HKD)", f"{avg_price:,}")
                else:
                    st.metric("Average Price", "N/A")
            
            # Calculate average area (excluding 'N/A' values)
            areas = []
            for p in st.session_state.properties_data:
                area_str = p.get('Net Area (sqft)', 'N/A')
                if area_str != 'N/A':
                    try:
                        area = int(area_str)
                        areas.append(area)
                    except:
                        pass
            
            with col3:
                if areas:
                    avg_area = sum(areas) // len(areas)
                    st.metric("Average Area (sqft)", f"{avg_area}")
                else:
                    st.metric("Average Area (sqft)", "N/A")
        else:
            st.info("No property data could be extracted. The search found properties but extraction failed.")
    
    elif st.session_state.search_performed and st.session_state.extract_clicked:
        st.info("No property data could be extracted.")

def main():
    st.set_page_config(page_title="Hong Kong Property Scraper")
    
    st.header("**Hong Kong Property Scraper**", text_alignment="center")
    st.caption("Search both rental and sale properties")
    
    # Create tabs
    tab1, tab2 = st.tabs(["Home", "Property Search"])
    
    with tab1:
        show_home_page()
    
    with tab2:
        show_property_search()
    
    # Cleanup on session end
    import atexit
    
    def cleanup():
        if 'scraper' in st.session_state and st.session_state.scraper:
            st.session_state.scraper.close()
    
    atexit.register(cleanup)

if __name__ == "__main__":
    main()
