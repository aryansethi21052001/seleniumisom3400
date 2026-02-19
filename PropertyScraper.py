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

class PropertyScraper:
    def __init__(self):
        """Initialise WebDriver"""
        try:
            self.service = Service(ChromeDriverManager().install())
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            self.driver = webdriver.Chrome(service=self.service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            self.url = "https://www.squarefoot.com.hk/en/rent" 
            self.driver.get(self.url)
        except Exception as e:
            st.error(f"Error setting up WebDriver: {e}")
            raise
    
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
    
    def extract_all_property_data(self, district):
        """
        Extract data from all property listings across all pages.
        """
        all_properties_data = []
        current_page = 1
        
        try:
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
                st.warning(f"Invalid {filter_name} choice: {choice}")
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
            
            st.warning(f"Option with data-value '{data_value}' not found for {filter_name}")
            return False
            
        except Exception as e:
            st.error(f"Error applying {filter_name} filter: {e}")
            return False
    
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
            
            if "results of property for lease" in results_text:
                # Extract just the number
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
            st.error(f"Error extracting property name: {e}")
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
                    except Exception as e:
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
                    except Exception as e:
                        property_data['Street Address'] = 'N/A'
                    
                    # 4. RENTAL PRICE - Extract property rental prices
                    try:
                        price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc.rentDesc')
                        price_text = price_element.text.strip()
                        # Remove "Lease HKD$" and keep just the number
                        # Example: "Lease HKD$23,900" -> "23,900"
                        property_data['Monthly Rental Price (in HKD)'] = price_text.replace('Lease HKD$', '').strip()   
                    except Exception as e:
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
                                # Splitting it makes the text become for example ["452", "ft²", " 2", "1"]
                                # 1. Net Area (first number before ft²)
                                if len(parts) > 0:
                                    property_data['Net Area (sqft)'] = parts[0]  # e.g., "452"
                                
                                # 2. Bedrooms (third element, index 2)
                                if len(parts) > 2:
                                    property_data['Number of Bedrooms'] = parts[2]
                                
                                # 3. Bathrooms (fourth element, index 3)
                                if len(parts) > 3:
                                    property_data['Number of Bathrooms'] = parts[3]
                                
                                break  # Found the right header, exit loop
                        
                        # Set defaults if not found
                        if 'Net Area (sqft)' not in property_data:
                            property_data['Net Area (sqft)'] = 'N/A'
                        if 'Number of Bedrooms' not in property_data:
                            property_data['Number of Bedrooms'] = 'N/A'
                        if 'Number of Bathrooms' not in property_data:
                            property_data['Number of Bathrooms'] = 'N/A'     
                    except Exception as e:
                        property_data['Net Area (sqft)'] = 'N/A'
                        property_data['Number of Bedrooms'] = 'N/A'
                        property_data['Number of Bathrooms'] = 'N/A'
                    
                    # 8. URL - Extract from img.detail_page href attribute
                    try:
                        # Find the image element
                        img_element = item.find_element(By.CSS_SELECTOR, 'img.desktop_myimage.detail_page')
                        # Get the href attribute which contains the URL
                        property_data['URL'] = img_element.get_attribute('href')
                    except Exception as e:
                        property_data['URL'] = 'N/A'
                    
                    # Add to list
                    properties_data.append(property_data)
                    
                except Exception as e:
                    # If we can't extract data from this property, skip it
                    continue
            
        except Exception as e:
            st.error(f"Error extracting property data: {e}")
        
        return properties_data
    
    def save_to_csv(self, properties_data, filename):
        """
        Save extracted property data to a CSV file.
        
        Args:
            properties_data: List of dictionaries containing property data
            filename: The filename to save to
        """
        if not properties_data:
            st.warning("No data to save.")
            return False
        
        try:
            # Add .csv extension if not present
            if not filename.endswith('.csv'):
                filename = filename + '.csv'
            
            # Define headers
            headers = [
                "District", "Name", "Street Address", "Monthly Rental Price (in HKD)", 
                "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"
            ]
            
            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                for property_data in properties_data:
                    writer.writerow(property_data)
            
            return filename
            
        except Exception as e:
            st.error(f"Error saving to CSV: {e}")
            return None
    
    def close(self):
        """Close the WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()

def list_csv_files():
    """List all CSV files in current directory."""
    csv_files = []
    for file in os.listdir('.'):
        if file.endswith('.csv'):
            csv_files.append(file)
    return csv_files

def main():
    st.title("Hong Kong Rental Property Scraper")
    
    # Initialize session state
    if 'scraper' not in st.session_state:
        st.session_state.scraper = None
    if 'properties_data' not in st.session_state:
        st.session_state.properties_data = None
    if 'search_completed' not in st.session_state:
        st.session_state.search_completed = False
    
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
        
        property_type = st.selectbox("Property Type", property_type_options, index=0)
        budget = st.selectbox("Monthly Budget (HKD)", budget_options, index=0)
        
        # Only show area and room filters if property type is not Carpark
        if property_type != "Carpark":
            area = st.selectbox("Saleable Area", area_options, index=0)
            rooms = st.selectbox("Number of Rooms", room_options, index=0)
        
        district = st.text_input("District Name", placeholder="e.g., Central, Causeway Bay")
        
        search_button = st.button("Search Properties", type="primary")
    
    # Main content area
    if search_button and district:
        if not district:
            st.warning("Please enter a district name.")
        else:
            try:
                # Initialize scraper if not already done
                if st.session_state.scraper is None:
                    with st.spinner("Initializing web scraper..."):
                        st.session_state.scraper = PropertyScraper()
                        st.success("Web scraper initialized successfully!")
                
                scraper = st.session_state.scraper
                
                # Apply filters
                with st.spinner("Applying filters..."):
                    # Property type filter
                    property_type_choice = property_type_mapping[property_type]
                    scraper.apply_generic_filter("mainType", property_type_choice, 
                                                {property_type_choice: property_type_mapping[property_type]}, 
                                                "Property Type")
                    
                    # Budget filter
                    budget_choice = budget_mapping[budget]
                    scraper.apply_generic_filter("price", budget_choice, 
                                                {budget_choice: budget_mapping[budget]}, 
                                                "Monthly Rent Budget")
                    
                    # Area filter (if applicable)
                    if property_type != "Carpark":
                        area_choice = area_mapping[area]
                        scraper.apply_generic_filter("areaRange", area_choice, 
                                                    {area_choice: area_mapping[area]}, 
                                                    "Saleable Area")
                    
                    # Room filter (if applicable)
                    if property_type != "Carpark":
                        room_choice = list(room_mapping.keys()).index(rooms) + 1
                        room_value = room_mapping[rooms]
                        scraper.apply_generic_filter("roomRange", str(room_choice), 
                                                    {str(room_choice): room_value}, 
                                                    "Number of Rooms")
                
                # Search district
                with st.spinner(f"Searching for properties in {district}..."):
                    property_count = scraper.search_district(district)
                
                if property_count > 0:
                    st.success(f"Found {property_count:,} properties matching your criteria.")
                    
                    # Extract data option
                    if st.button("Extract Property Data"):
                        with st.spinner("Extracting property data..."):
                            properties_data = scraper.extract_all_property_data(district)
                        
                        if properties_data:
                            st.session_state.properties_data = properties_data
                            st.session_state.search_completed = True
                            
                            # Display data in a table
                            st.subheader("Extracted Property Data")
                            df = pd.DataFrame(properties_data)
                            st.dataframe(df, use_container_width=True)
                            
                            # Save options
                            st.subheader("Save Options")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                filename = st.text_input("Enter filename to save as (without .csv)", 
                                                        value="properties")
                            
                            with col2:
                                if st.button("Save to CSV"):
                                    if filename:
                                        saved_file = scraper.save_to_csv(properties_data, filename)
                                        if saved_file:
                                            st.success(f"Data saved to {saved_file}")
                                            
                                            # Provide download button
                                            with open(saved_file, 'r', encoding='utf-8') as f:
                                                csv_data = f.read()
                                            st.download_button(
                                                label="Download CSV",
                                                data=csv_data,
                                                file_name=saved_file,
                                                mime="text/csv"
                                            )
                                    else:
                                        st.warning("Please enter a filename.")
                            
                            # Show existing CSV files
                            csv_files = list_csv_files()
                            if csv_files:
                                st.subheader("Existing CSV Files")
                                for file in csv_files:
                                    st.text(file)
                        else:
                            st.warning("No property data could be extracted.")
                else:
                    st.warning("No properties found in this district.")
                    
            except Exception as e:
                st.error(f"An error occurred: {e}")
    
    # Display previously extracted data if available
    elif st.session_state.search_completed and st.session_state.properties_data:
        st.subheader("Previously Extracted Property Data")
        df = pd.DataFrame(st.session_state.properties_data)
        st.dataframe(df, use_container_width=True)
    
    # Instructions
    if not st.session_state.search_completed and not search_button:
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
            8. Save the data to a CSV file for later use
            """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
    finally:
        # Clean up WebDriver when the app is closed
        if 'scraper' in st.session_state and st.session_state.scraper:
            st.session_state.scraper.close()
