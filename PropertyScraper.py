import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import csv
import os
import pandas as pd
import platform
import subprocess
import tempfile

def find_chromedriver():
    """Find chromedriver in common locations"""
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/lib/chromium/chromedriver',
        '/usr/lib/chromium-browser/chromedriver',
        '/snap/bin/chromium.chromedriver',
        '/usr/local/bin/chromedriver'
    ]
    
    # Try common paths
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try using 'which' command
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    return None

class PropertyScraper:
    def __init__(self):
        """Initialise WebDriver"""
        self.driver = None
        self.wait = None
        self.url = None
        
    def setup_driver(self):
        """Initialize the Chrome WebDriver with cloud-compatible options"""
        try:
            chrome_options = Options()
            
            # Essential options for cloud environment
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Additional options for stability
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--remote-debugging-port=9222')
            
            system = platform.system()
            
            if system == 'Linux':
                # For Streamlit Cloud - try multiple binary locations
                chromium_paths = [
                    '/usr/bin/chromium',
                    '/usr/bin/chromium-browser',
                    '/snap/bin/chromium',
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable'
                ]
                
                binary_found = False
                for path in chromium_paths:
                    if os.path.exists(path):
                        chrome_options.binary_location = path
                        binary_found = True
                        break
                
                if not binary_found:
                    st.error("Chromium/Chrome browser not found. Please ensure it's installed.")
                    return False
                
                # Find chromedriver
                chromedriver_path = find_chromedriver()
                
                if chromedriver_path:
                    try:
                        service = Service(executable_path=chromedriver_path)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        self.wait = WebDriverWait(self.driver, 20)
                        self.url = "https://www.squarefoot.com.hk/en/rent"
                        return True
                    except Exception as e:
                        st.error(f"Error creating driver with found chromedriver: {str(e)}")
                        return False
                else:
                    st.error("ChromeDriver not found. Please ensure chromium-driver is installed.")
                    return False
            
            else:
                # For local Windows/Mac development
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.wait = WebDriverWait(self.driver, 20)
                    self.url = "https://www.squarefoot.com.hk/en/rent"
                    return True
                except:
                    # Fallback to selenium-manager
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.wait = WebDriverWait(self.driver, 20)
                    self.url = "https://www.squarefoot.com.hk/en/rent"
                    return True
            
        except Exception as e:
            st.error(f"Error setting up WebDriver: {str(e)}")
            return False
    
    def check_driver_connection(self):
        """Check if driver is still connected and responsive"""
        try:
            # Try a simple operation to check connection
            self.driver.current_url
            return True
        except:
            return False

    def ensure_driver_connected(self):
        """Ensure driver is connected, reconnect if necessary"""
        if self.driver is None or not self.check_driver_connection():
            st.warning("WebDriver disconnected. Reconnecting...")
            return self.setup_driver()
        return True
    
    def load_website(self):
        """Load the target website"""
        try:
            self.driver.get(self.url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            time.sleep(3)
            return True
        except Exception as e:
            st.error(f"Error loading website: {e}")
            return False
    
    def get_total_pages(self):
        """
        Get the total number of pages from pagination.
        Returns the maximum page number or 1 if no pagination found.
        """
        try:
            if not self.ensure_driver_connected():
                return 1
            
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
            if not self.ensure_driver_connected():
                return False
            
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
    
    def extract_all_property_data(self, district):
        """
        Extract data from all property listings across all pages.
        """
        all_properties_data = []
        current_page = 1
        
        try:
            if not self.ensure_driver_connected():
                st.error("Driver disconnected. Please try again.")
                return []
            
            total_pages = self.get_total_pages()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            while current_page <= total_pages:
                status_text.text(f"Extracting page {current_page}/{total_pages}...")
                
                page_properties = self.extract_property_data(district)
                all_properties_data.extend(page_properties)
                
                progress_bar.progress(current_page / total_pages)
                
                if current_page >= total_pages:
                    break
                
                if not self.go_to_next_page():
                    break
                
                current_page += 1
            
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"Error during extraction: {e}")
        
        return all_properties_data

    def apply_generic_filter(self, filter_attr, choice, mapping, filter_name):
        """
        Generic helper method to apply any filter on the website.
        """
        try:
            if not self.ensure_driver_connected():
                st.error(f"Driver disconnected while applying {filter_name} filter.")
                return False
            
            if choice not in mapping:
                st.warning(f"Invalid {filter_name} choice: {choice}")
                return False
            
            data_value = mapping[choice]
            
            # Wait for filter container with retry
            filter_container = None
            for attempt in range(3):
                try:
                    filter_container = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'div[attr="{filter_attr}"]')))
                    break
                except:
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    else:
                        st.error(f"Could not find {filter_name} filter container")
                        return False
            
            options = filter_container.find_elements(By.CSS_SELECTOR, '.ui.groupTop.horizontal.list.level0 a.item')
            
            for option in options:
                option_data_value = option.get_attribute('data-value')
                if option_data_value == data_value:
                    option.click()
                    time.sleep(2)
                    return True
            
            st.warning(f"Option with data-value '{data_value}' not found for {filter_name}")
            return False
            
        except Exception as e:
            st.error(f"Error applying {filter_name} filter: {e}")
            return False
    
    def search_district(self, district):
        """Search for properties in the specified district."""
        try:
            if not self.ensure_driver_connected():
                st.error("Driver disconnected while searching district.")
                return 0
            
            search_input = self.wait.until(EC.element_to_be_clickable((By.NAME, 'searchText_temp')))
            search_input.clear()
            time.sleep(1)
            search_input.send_keys(district)
            time.sleep(1)
            
            search_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'searchwords_btn')))
            search_button.click()
            time.sleep(5)
            
            # Get the results count
            try:
                results_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[style*="float: left"]')))
                results_text = results_element.text.strip()
                
                if "results of property for lease" in results_text:
                    # Extract just the number
                    num_str = results_text.split()[0].replace(',', '')
                    try:
                        property_count = int(num_str)
                        return property_count
                    except ValueError:
                        return 0
            except:
                # Alternative method if the specific element isn't found
                try:
                    # Look for any element containing the results text
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'results of property for lease')]")
                    if elements:
                        text = elements[0].text.strip()
                        num_str = text.split()[0].replace(',', '')
                        return int(num_str)
                except:
                    pass
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
                
        except Exception:
            return 'N/A'
    
    def extract_property_data(self, district):
        """
        Extract data from all property listings on the current page.
        """
        properties_data = []
        
        try:
            if not self.ensure_driver_connected():
                return []
            
            # Wait for property listings to load
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
                time.sleep(2)
            except:
                st.warning("No property items found on this page")
                return []
            
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
                    except Exception:
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
                    except Exception:
                        property_data['Street Address'] = 'N/A'
                    
                    # 4. RENTAL PRICE - Extract property rental prices
                    try:
                        price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc.rentDesc')
                        price_text = price_element.text.strip()
                        property_data['Monthly Rental Price (in HKD)'] = price_text.replace('Lease HKD$', '').strip()   
                    except Exception:
                        property_data['Monthly Rental Price (in HKD)'] = 'N/A'
        
                    # 5, 6, 7. Extract Net Area, Bedrooms, and Bathrooms
                    try:
                        # Find the header with ft²
                        header_divs = item.find_elements(By.CSS_SELECTOR, 'div.header')
                        
                        for header in header_divs:
                            text = header.text.strip()
                            
                            if 'ft²' in text:
                                # Split the text by whitespace
                                parts = text.split()
                                if len(parts) > 0:
                                    property_data['Net Area (sqft)'] = parts[0]
                                if len(parts) > 2:
                                    property_data['Number of Bedrooms'] = parts[2]
                                if len(parts) > 3:
                                    property_data['Number of Bathrooms'] = parts[3]
                                break
                        
                        if 'Net Area (sqft)' not in property_data:
                            property_data['Net Area (sqft)'] = 'N/A'
                        if 'Number of Bedrooms' not in property_data:
                            property_data['Number of Bedrooms'] = 'N/A'
                        if 'Number of Bathrooms' not in property_data:
                            property_data['Number of Bathrooms'] = 'N/A'     
                    except Exception:
                        property_data['Net Area (sqft)'] = 'N/A'
                        property_data['Number of Bedrooms'] = 'N/A'
                        property_data['Number of Bathrooms'] = 'N/A'
                    
                    # 8. URL - Extract from img.detail_page href attribute
                    try:
                        img_element = item.find_element(By.CSS_SELECTOR, 'img.desktop_myimage.detail_page')
                        property_data['URL'] = img_element.get_attribute('href')
                    except Exception:
                        property_data['URL'] = 'N/A'
                    
                    properties_data.append(property_data)
                    
                except Exception:
                    continue
            
        except Exception as e:
            st.error(f"Error extracting property data: {e}")
        
        return properties_data
    
    def save_to_csv(self, properties_data, filename):
        """
        Save extracted property data to a CSV file.
        """
        if not properties_data:
            st.warning("No data to save.")
            return None
        
        try:
            # Add .csv extension if not present
            if not filename.endswith('.csv'):
                filename = filename + '.csv'
            
            # Use temp directory for cloud compatibility
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, filename)
            
            # Define headers
            headers = [
                "District", "Name", "Street Address", "Monthly Rental Price (in HKD)", 
                "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"
            ]
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                for property_data in properties_data:
                    writer.writerow(property_data)
            
            return filepath
            
        except Exception as e:
            st.error(f"Error saving to CSV: {e}")
            return None
    
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.wait = None

def main():
    st.title("Hong Kong Rental Property Scraper")
    
    # Initialize session state
    if 'scraper' not in st.session_state:
        st.session_state.scraper = PropertyScraper()
    if 'properties_data' not in st.session_state:
        st.session_state.properties_data = None
    if 'driver_initialized' not in st.session_state:
        st.session_state.driver_initialized = False
    if 'current_page_loaded' not in st.session_state:
        st.session_state.current_page_loaded = False
    if 'extraction_in_progress' not in st.session_state:
        st.session_state.extraction_in_progress = False
    if 'extraction_complete' not in st.session_state:
        st.session_state.extraction_complete = False
    
    # Property type mapping
    property_type_mapping = {
        "All": "0",
        "Apartment": "5",
        "Carpark": "6",
        "Office": "7",
        "Shop": "8"
    }
    
    property_type_options = ["All", "Apartment", "Carpark", "Office", "Shop"]
    
    # Budget mapping
    budget_mapping = {
        "No preference": "0",
        "Below HK$ 10,000": "1",
        "HK$ 10,000 - HK$ 20,000": "2",
        "HK$ 20,000 - HK$ 40,000": "3",
        "HK$ 40,000 - HK$ 60,000": "4",
        "HK$ 60,000 - HK$ 80,000": "5",
        "Above HK$ 80,000": "6"
    }
    
    budget_options = list(budget_mapping.keys())
    
    # Area mapping
    area_mapping = {
        "No preference": "0",
        "Below 300 ft²": "1",
        "300 - 500 ft²": "2",
        "500 - 1000 ft²": "3",
        "1000 - 2000 ft²": "4",
        "Above 2000 ft²": "5"
    }
    
    area_options = list(area_mapping.keys())
    
    # Room mapping
    room_mapping = {
        "No preference": "0",
        "Studio": "STUDIO",
        "1 room": "1",
        "2 rooms": "2",
        "3 rooms": "3",
        "4 rooms": "4",
        "5+ rooms": "5PLUS"
    }
    
    room_options = list(room_mapping.keys())
    
    # Sidebar for filters
    with st.sidebar:
        st.header("Search Filters")
        
        property_type = st.selectbox("Property Type", property_type_options, index=0, key="property_type")
        budget = st.selectbox("Monthly Budget (HKD)", budget_options, index=0, key="budget")
        
        # Only show area and room filters if property type is not Carpark
        if property_type != "Carpark":
            area = st.selectbox("Saleable Area", area_options, index=0, key="area")
            rooms = st.selectbox("Number of Rooms", room_options, index=0, key="rooms")
        
        district = st.text_input("District Name", placeholder="e.g., Central, Causeway Bay", key="district")
        
        col1, col2 = st.columns(2)
        with col1:
            search_button = st.button("Search Properties", type="primary", key="search_btn")
        with col2:
            if st.button("Reset Connection", key="reset_btn"):
                if st.session_state.driver_initialized:
                    st.session_state.scraper.close_driver()
                st.session_state.driver_initialized = False
                st.session_state.current_page_loaded = False
                st.session_state.extraction_in_progress = False
                st.session_state.extraction_complete = False
                st.session_state.properties_data = None
                st.success("Connection reset. Please try again.")
                st.rerun()
    
    # Main content area
    if search_button and district:
        if not district:
            st.warning("Please enter a district name.")
        else:
            try:
                # Initialize driver if not already done
                if not st.session_state.driver_initialized:
                    with st.spinner("Initializing web scraper..."):
                        if st.session_state.scraper.setup_driver():
                            st.session_state.driver_initialized = True
                            st.success("Web scraper initialized successfully!")
                            
                            # Load the website
                            if st.session_state.scraper.load_website():
                                st.session_state.current_page_loaded = True
                                st.success("Website loaded successfully!")
                            else:
                                st.error("Failed to load website.")
                                st.stop()
                        else:
                            st.error("Failed to initialize web scraper. Please check the error messages above.")
                            st.stop()
                
                scraper = st.session_state.scraper
                
                # Ensure driver is connected and page is loaded
                if not scraper.ensure_driver_connected():
                    st.error("WebDriver disconnected. Please reset the connection and try again.")
                    st.stop()
                
                if not st.session_state.current_page_loaded:
                    if scraper.load_website():
                        st.session_state.current_page_loaded = True
                    else:
                        st.error("Failed to load website.")
                        st.stop()
                
                # Apply filters
                filter_success = True
                with st.spinner("Applying filters..."):
                    # Property type filter
                    if not scraper.apply_generic_filter("mainType", property_type_mapping[property_type], 
                                                       {property_type_mapping[property_type]: property_type_mapping[property_type]}, 
                                                       "Property Type"):
                        filter_success = False
                    
                    # Budget filter
                    if not scraper.apply_generic_filter("price", budget_mapping[budget], 
                                                       {budget_mapping[budget]: budget_mapping[budget]}, 
                                                       "Monthly Rent Budget"):
                        filter_success = False
                    
                    # Area filter (if applicable)
                    if property_type != "Carpark" and filter_success:
                        if not scraper.apply_generic_filter("areaRange", area_mapping[area], 
                                                           {area_mapping[area]: area_mapping[area]}, 
                                                           "Saleable Area"):
                            filter_success = False
                    
                    # Room filter (if applicable)
                    if property_type != "Carpark" and filter_success:
                        room_value = room_mapping[rooms]
                        room_choice = list(room_mapping.values()).index(room_value)
                        if not scraper.apply_generic_filter("roomRange", str(room_choice), 
                                                           {str(room_choice): room_value}, 
                                                           "Number of Rooms"):
                            filter_success = False
                
                if not filter_success:
                    st.warning("Some filters could not be applied. Continuing with applied filters...")
                
                # Search district
                with st.spinner(f"Searching for properties in {district}..."):
                    property_count = scraper.search_district(district)
                
                if property_count > 0:
                    st.success(f"Found {property_count:,} properties matching your criteria.")
                    
                    # Store search results in session state
                    st.session_state.property_count = property_count
                    st.session_state.current_district = district
                    
                    # Extract data option
                    col1, col2 = st.columns(2)
                    with col1:
                        extract_button = st.button("Extract Property Data", key="extract_btn", type="primary")
                    with col2:
                        if st.button("Cancel", key="cancel_btn"):
                            st.session_state.extraction_in_progress = False
                            st.session_state.extraction_complete = False
                            st.rerun()

                    # if extract_button and not st.session_state.extraction_in_progress:
                    #     st.session_state.extraction_in_progress = True
                    #     st.rerun()

                    if st.session_state.extraction_in_progress:
                        with st.spinner("Extracting property data... This may take a few minutes."):
                            properties_data = scraper.extract_all_property_data(district)
                        
                        if properties_data:
                            st.session_state.properties_data = properties_data
                            st.session_state.extraction_complete = True
                            st.session_state.extraction_in_progress = False
                            st.rerun()
                        else:
                            st.warning("No property data could be extracted.")
                            st.session_state.extraction_in_progress = False
                else:
                    st.warning("No properties found in this district.")
                    
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.info("Try clicking 'Reset Connection' and try again.")

    # Results container
    results_container = st.container()

    with results_container:
        # Display extracted data if available
        if st.session_state.properties_data is not None and st.session_state.extraction_complete:
            st.subheader("Extracted Property Data")
            df = pd.DataFrame(st.session_state.properties_data)
            st.dataframe(df, use_container_width=True)
            
            # Save options
            st.subheader("Save Options")
            
            filename = st.text_input("Enter filename to save as (without .csv)", 
                                    value="properties", key="filename_input")
            
            if st.button("Save and Download CSV", key="save_btn"):
                if filename:
                    saved_file = st.session_state.scraper.save_to_csv(st.session_state.properties_data, filename)
                    if saved_file:
                        st.success("Data saved temporarily!")
                        
                        # Provide download button
                        with open(saved_file, 'r', encoding='utf-8') as f:
                            csv_data = f.read()
                        st.download_button(
                            label="Download CSV",
                            data=csv_data,
                            file_name=filename + '.csv',
                            mime="text/csv",
                            key="download_btn"
                        )
                else:
                    st.warning("Please enter a filename.")
            
            # Add a clear button
            if st.button("Clear Results", key="clear_btn"):
                st.session_state.properties_data = None
                st.session_state.extraction_complete = False
                st.rerun()

    # Instructions
    if not st.session_state.properties_data and not search_button and not st.session_state.extraction_in_progress:
        st.info("Use the filters in the sidebar to search for rental properties in Hong Kong.")
        
        with st.expander("How to use this app"):
            st.write("""
            1. Select your preferred property type from the sidebar
            2. Choose your monthly budget range
            3. If applicable, select desired area size and number of rooms
            4. Enter a district name (e.g., Central, Causeway Bay, Tsim Sha Tsui)
            5. Click 'Search Properties' to begin
            6. After searching, click 'Extract Property Data' to scrape detailed information
            7. View the extracted data in the table
            8. Save and download the data as a CSV file
            
            If you encounter connection issues, click 'Reset Connection' and try again.
            """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
    # finally:
    #     # Clean up WebDriver when the app is closed
    #     if 'scraper' in st.session_state and hasattr(st.session_state.scraper, 'close_driver'):
    #         st.session_state.scraper.close_driver()
