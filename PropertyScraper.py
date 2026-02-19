import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import os
import pandas as pd
from tempfile import NamedTemporaryFile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PropertyScraper:
    def __init__(self):
        """Initialise WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Use webdriver-manager to handle driver installation
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)  # Increased timeout
            self.url = "https://www.squarefoot.com.hk/en/rent" 
            
            logger.info("Navigating to URL")
            self.driver.get(self.url)
            
            # Wait for page to load completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)  # Additional wait for dynamic content
            
        except Exception as e:
            st.error(f"Error setting up WebDriver: {e}")
            logger.error(f"WebDriver setup error: {e}")
            raise
    
    def get_total_pages(self):
        """
        Get the total number of pages from pagination.
        """
        try:
            time.sleep(2)
            
            # Try multiple selectors for pagination
            selectors = [
                'div.ui.borderless.menu.pagination',
                'div.pagination',
                'div[class*="pagination"]',
                'a.item[attr1]'
            ]
            
            pagination = None
            for selector in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    pagination = elements[0]
                    break
            
            if not pagination:
                logger.info("No pagination found, assuming single page")
                return 1
            
            # Find all page numbers
            page_items = pagination.find_elements(By.CSS_SELECTOR, 'a.item[attr1]')
            
            page_numbers = []
            for item in page_items:
                attr_value = item.get_attribute('attr1')
                if attr_value and attr_value.isdigit():
                    page_numbers.append(int(attr_value))
            
            if page_numbers:
                total_pages = max(page_numbers)
                logger.info(f"Total pages found: {total_pages}")
                return total_pages
            
            return 1
                    
        except Exception as e:
            logger.error(f"Error getting total pages: {e}")
            return 1
    
    def go_to_next_page(self):
        """
        Click the next page button.
        """
        try:
            time.sleep(2)
            
            # Find next button with multiple selectors
            next_selectors = [
                'a.item[attr1="plus"]',
                'a.item.next',
                'a[aria-label="Next page"]',
                'button.next'
            ]
            
            next_button = None
            for selector in next_selectors:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if buttons:
                    next_button = buttons[0]
                    break
            
            if not next_button:
                logger.info("No next page button found")
                return False
            
            # Scroll to button and click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(1)
            next_button.click()
            
            # Wait for new page to load
            time.sleep(3)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
            
            return True
            
        except Exception as e:
            logger.error(f"Error going to next page: {e}")
            return False
    
    def search_district(self, district):
        """Search for properties in the specified district."""
        try:
            # Wait for search input to be clickable
            search_input = self.wait.until(EC.element_to_be_clickable((By.NAME, 'searchText_temp')))
            search_input.clear()
            time.sleep(0.5)
            search_input.send_keys(district)
            
            # Click search button
            search_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'searchwords_btn')))
            search_button.click()
            
            # Wait for results to load
            time.sleep(5)
            
            # Try multiple selectors for results count
            count_selectors = [
                'div[style*="float: left"]',
                'div.results-count',
                'span.count',
                'div.result-stats'
            ]
            
            for selector in count_selectors:
                try:
                    results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    results_text = results_element.text.strip()
                    
                    # Try to extract number from text
                    import re
                    numbers = re.findall(r'\d+', results_text.replace(',', ''))
                    if numbers:
                        property_count = int(numbers[0])
                        logger.info(f"Found {property_count} properties")
                        return property_count
                except:
                    continue
            
            # If we can't find the count but property items exist, count them
            property_items = self.driver.find_elements(By.CSS_SELECTOR, 'div.item.property_item')
            if property_items:
                logger.info(f"Found {len(property_items)} property items on page")
                return len(property_items)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error searching district '{district}': {e}")
            return 0
    
    def extract_property_data(self, district):
        """
        Extract data from all property listings on the current page.
        """
        properties_data = []
        
        try:
            # Wait for property listings with multiple selectors
            property_selectors = [
                'div.item.property_item',
                'div.property-item',
                'div.listing-item'
            ]
            
            property_items = []
            for selector in property_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if items:
                        property_items = items
                        logger.info(f"Found {len(items)} properties using selector: {selector}")
                        break
                except:
                    continue
            
            if not property_items:
                logger.warning("No property items found on page")
                # Debug: print page source snippet
                page_source = self.driver.page_source[:1000]
                logger.debug(f"Page source snippet: {page_source}")
                return []
            
            for item in property_items:
                property_data = {}
                
                try:
                    # DISTRICT
                    property_data['District'] = district
                    
                    # NAME - Try multiple selectors
                    name_selectors = [
                        'div.header.cat',
                        'h3.title',
                        'div.property-title',
                        'a.title'
                    ]
                    
                    property_name = 'N/A'
                    for selector in name_selectors:
                        try:
                            name_elem = item.find_element(By.CSS_SELECTOR, selector)
                            full_text = name_elem.text.strip()
                            if full_text:
                                # Clean up the name
                                if full_text.startswith(district):
                                    property_name = full_text[len(district):].strip()
                                else:
                                    property_name = full_text
                                break
                        except:
                            continue
                    property_data['Name'] = property_name
                    
                    # STREET ADDRESS
                    address_selectors = [
                        'div.meta',
                        'div.address',
                        'span.location',
                        'div.property-address'
                    ]
                    
                    address = 'N/A'
                    for selector in address_selectors:
                        try:
                            meta_divs = item.find_elements(By.CSS_SELECTOR, selector)
                            if meta_divs:
                                address = meta_divs[0].text.strip()
                                break
                        except:
                            continue
                    property_data['Street Address'] = address
                    
                    # RENTAL PRICE
                    price_selectors = [
                        'span.priceDesc.rentDesc',
                        'span.price',
                        'div.price',
                        'span.rent'
                    ]
                    
                    price = 'N/A'
                    for selector in price_selectors:
                        try:
                            price_elem = item.find_element(By.CSS_SELECTOR, selector)
                            price_text = price_elem.text.strip()
                            if price_text:
                                # Clean up price text
                                price = price_text.replace('Lease HKD$', '').replace('HKD', '').replace('$', '').strip()
                                break
                        except:
                            continue
                    property_data['Monthly Rental Price (in HKD)'] = price
                    
                    # AREA, BEDROOMS, BATHROOMS
                    area = 'N/A'
                    bedrooms = 'N/A'
                    bathrooms = 'N/A'
                    
                    try:
                        # Look for elements containing ft²
                        area_selectors = [
                            'div.header',
                            'span.area',
                            'div.size',
                            'div.property-details'
                        ]
                        
                        for selector in area_selectors:
                            elements = item.find_elements(By.CSS_SELECTOR, selector)
                            for elem in elements:
                                text = elem.text.strip()
                                if 'ft²' in text or 'sqft' in text:
                                    # Split by whitespace and clean
                                    parts = text.split()
                                    if parts:
                                        # First part is usually area
                                        area = parts[0].replace(',', '')
                                        
                                        # Look for bedroom/bathroom indicators
                                        text_lower = text.lower()
                                        if 'bed' in text_lower:
                                            for i, part in enumerate(parts):
                                                if 'bed' in part.lower():
                                                    bedrooms = parts[i-1] if i > 0 else bedrooms
                                                if 'bath' in part.lower():
                                                    bathrooms = parts[i-1] if i > 0 else bathrooms
                                    break
                    except Exception as e:
                        logger.debug(f"Error extracting area details: {e}")
                    
                    property_data['Net Area (sqft)'] = area
                    property_data['Number of Bedrooms'] = bedrooms
                    property_data['Number of Bathrooms'] = bathrooms
                    
                    # URL
                    url_selectors = [
                        'img.desktop_myimage.detail_page',
                        'a.property-link',
                        'img[src*="property"]'
                    ]
                    
                    url = 'N/A'
                    for selector in url_selectors:
                        try:
                            img_element = item.find_element(By.CSS_SELECTOR, selector)
                            url = img_element.get_attribute('href') or img_element.get_attribute('src')
                            if url and url != 'N/A':
                                break
                        except:
                            continue
                    property_data['URL'] = url
                    
                    # Only add if we have at least some data
                    if property_data['Name'] != 'N/A' or property_data['Monthly Rental Price (in HKD)'] != 'N/A':
                        properties_data.append(property_data)
                        logger.debug(f"Extracted property: {property_data['Name']}")
                    
                except Exception as e:
                    logger.error(f"Error extracting individual property: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting property data: {e}")
            st.error(f"Error extracting data: {e}")
        
        logger.info(f"Extracted {len(properties_data)} properties from current page")
        return properties_data
    
    # ... [keep other methods like apply_generic_filter, apply_property_type_filter, etc. the same]
    
    def close(self):
        """Close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()

def main():
    st.set_page_config(page_title="Hong Kong Rental Property Scraper", layout="wide")
    
    st.title("Hong Kong Rental Property Scraper")
    
    # Add debug mode toggle
    debug_mode = st.sidebar.checkbox("Debug Mode", value=False)
    
    # Initialize session state
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
    
    # Sidebar for filters
    with st.sidebar:
        st.header("Search Filters")
        
        property_type = st.selectbox(
            "Property Type",
            ["All", "Apartment", "Carpark", "Office", "Shop"],
            key="property_type"
        )
        
        budget = st.selectbox(
            "Monthly Budget (HKD)",
            ["No preference", "Below 10,000", "10,000 - 20,000", 
             "20,000 - 40,000", "40,000 - 60,000", "60,000 - 80,000", 
             "Above 80,000"],
            key="budget"
        )
        
        if property_type != "Carpark":
            area = st.selectbox(
                "Saleable Area (sqft)",
                ["No preference", "Below 300", "300 - 500", "500 - 1000", 
                 "1000 - 2000", "Above 2000"],
                key="area"
            )
            rooms = st.selectbox(
                "Number of Rooms",
                ["No preference", "Studio", "1", "2", "3", "4", "5+"],
                key="rooms"
            )
        else:
            area = "No preference"
            rooms = "No preference"
        
        district = st.text_input("District Name (e.g., Central, Causeway Bay)", key="district_input")
        
        # Add a test connection button
        if st.button("Test Connection"):
            try:
                scraper = PropertyScraper()
                st.success("Successfully connected to website!")
                scraper.close()
            except Exception as e:
                st.error(f"Connection failed: {e}")
        
        search_button = st.button("Search Properties", type="primary", disabled=not district)
    
    # Main content area
    if search_button and district:
        with st.spinner("Initializing scraper..."):
            if st.session_state.scraper:
                st.session_state.scraper.close()
            
            try:
                st.session_state.scraper = PropertyScraper()
                
                # Apply filters with error handling
                filter_results = []
                filter_results.append(st.session_state.scraper.apply_property_type_filter(property_type))
                filter_results.append(st.session_state.scraper.apply_budget_filter(budget))
                
                if property_type != "Carpark":
                    filter_results.append(st.session_state.scraper.apply_area_filter(area))
                    filter_results.append(st.session_state.scraper.apply_room_filter(rooms))
                
                # Check if all filters were applied successfully
                if debug_mode:
                    st.write("Filter application results:", filter_results)
                
                # Search district
                property_count = st.session_state.scraper.search_district(district)
                st.session_state.property_count = property_count
                st.session_state.current_district = district
                
                if property_count > 0:
                    st.success(f"Found {property_count:,} properties")
                    st.session_state.search_performed = True
                    
                    # In debug mode, show a sample of the page
                    if debug_mode:
                        with st.expander("Debug Information"):
                            st.write("Page title:", st.session_state.scraper.driver.title)
                            st.write("Current URL:", st.session_state.scraper.driver.current_url)
                            
                            # Try to extract a sample property
                            sample_data = st.session_state.scraper.extract_property_data(district)
                            if sample_data:
                                st.write("Sample extracted data:", sample_data[:2])
                            else:
                                st.write("No sample data could be extracted")
                else:
                    st.warning("No properties found in this district")
                    st.session_state.search_performed = False
                    
            except Exception as e:
                st.error(f"Error during search: {e}")
                if debug_mode:
                    st.exception(e)
                st.session_state.search_performed = False
    
    # Show extract button if search was successful
    if st.session_state.search_performed and not st.session_state.extract_clicked and st.session_state.property_count > 0:
        if st.button("Extract Property Data", key="extract_button"):
            with st.spinner("Extracting property data... This may take a while..."):
                st.session_state.properties_data = st.session_state.scraper.extract_all_property_data(st.session_state.current_district)
                st.session_state.extract_clicked = True
                
                if st.session_state.properties_data:
                    st.success(f"Successfully extracted {len(st.session_state.properties_data)} properties!")
                else:
                    st.warning("No data was extracted. Try enabling debug mode to see more details.")
                st.rerun()
    
    # Display results
    if st.session_state.get('properties_data') is not None:
        if len(st.session_state.properties_data) > 0:
            st.header("Search Results")
            
            df = pd.DataFrame(st.session_state.properties_data)
            st.dataframe(df, use_container_width=True)
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Save to CSV", key="save_csv_button"):
                    filename = f"property_data_{st.session_state.current_district}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    saved_file = st.session_state.scraper.save_to_csv(st.session_state.properties_data, filename)
                    if saved_file:
                        st.success(f"Data saved to {saved_file}")
                        
                        with open(saved_file, 'rb') as f:
                            st.download_button(
                                label="Download CSV",
                                data=f,
                                file_name=saved_file,
                                mime='text/csv',
                                key="download_csv_button"
                            )
            
            # Display statistics
            st.header("Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Properties", len(st.session_state.properties_data))
            
            # Calculate average price
            prices = []
            for p in st.session_state.properties_data:
                price_str = p.get('Monthly Rental Price (in HKD)', 'N/A')
                if price_str != 'N/A':
                    try:
                        price = int(price_str.replace(',', ''))
                        prices.append(price)
                    except:
                        pass
            
            with col2:
                if prices:
                    avg_price = sum(prices) // len(prices)
                    st.metric("Average Price (HKD)", f"{avg_price:,}")
                else:
                    st.metric("Average Price (HKD)", "N/A")
            
            # Calculate average area
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
            st.info("No property data could be extracted. Try:")
            st.info("1. Enabling debug mode to see more details")
            st.info("2. Checking if the district name is correct")
            st.info("3. Trying a different district")
            st.info("4. Checking your internet connection")
    
    # Cleanup on session end
    if st.session_state.scraper:
        st.session_state.scraper.close()

if __name__ == "__main__":
    main()
