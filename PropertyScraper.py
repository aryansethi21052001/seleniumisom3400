import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import csv
import pandas as pd
import io
import re
import atexit

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
            
            # Set URL and price configuration based on transaction type
            self.transaction_type = transaction_type
            if transaction_type == "rent":
                self.url = "https://www.squarefoot.com.hk/en/rent"
                self.price_field = "Monthly Rental Price (in HKD)"
                self.price_css_selector = 'span.priceDesc.rentDesc'
                self.price_prefix_pattern = r'(?:Lease\s*HKD\$)?'
            else:  # buy
                self.url = "https://www.squarefoot.com.hk/en/buy"
                self.price_field = "Sale Price (in HKD Millions)"
                self.price_css_selector = 'span.priceDesc'
                self.price_prefix_pattern = r'(?:Sell\s*HKD\$)?'
            
            self.driver.get(self.url)
            time.sleep(2)
        except Exception as e:
            st.error(f"Error setting up WebDriver: {e}")
            raise

    def extract_price_from_text(self, price_text):
        """Extract numeric price from text like "Sell HKD$12.8 Millions" or "Lease HKD$50,000"."""
        if not price_text or price_text == 'N/A':
            return 'N/A'
        
        try:
            # Remove common prefixes
            cleaned = re.sub(r'(?:Lease|Sell|HKD\$)\s*', '', price_text).strip()
            
            if self.transaction_type == "rent":
                # Remove commas and return
                return cleaned.replace(',', '') if cleaned else 'N/A'
            else:
                # Extract just the number for buy properties
                number_match = re.search(r'([\d.]+)', cleaned)
                return number_match.group(1) if number_match else 'N/A'
        except Exception:
            return 'N/A'
    
    def get_total_pages(self):
        """Get the total number of pages."""
        try:
            time.sleep(2)
            pagination = self.driver.find_elements(By.CSS_SELECTOR, 'div.ui.borderless.menu.pagination')
            if not pagination:
                return 1
            
            page_items = pagination[0].find_elements(By.CSS_SELECTOR, 'a.item[attr1]')
            page_numbers = []
            
            for item in page_items:
                attr_value = item.get_attribute('attr1')
                if attr_value and attr_value.isdigit():
                    page_numbers.append(int(attr_value))
            
            return max(page_numbers) if page_numbers else 1
        except Exception as e:
            st.error(f"Error getting total pages: {e}")
            return 1
    
    def go_to_next_page(self):
        """Click the next page button."""
        try:
            time.sleep(1)
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a.item[attr1="plus"]')
            if not next_buttons:
                return False
            
            next_buttons[0].click()
            time.sleep(3)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
            return True
        except Exception as e:
            st.error(f"Error going to next page: {e}")
            return False
    
    def extract_all_property_data(self, district, total_properties):
        """Extract data from all property listings across all pages."""
        all_properties_data = []
        current_page = 1
    
        try:
            total_pages = self.get_total_pages()
            st.info(f"Total properties to scrape: {total_properties:,}")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            properties_scraped = 0
            
            while current_page <= total_pages:
                page_properties = self.extract_property_data(district.title())
                all_properties_data.extend(page_properties)
                properties_scraped += len(page_properties)
                
                status_text.text(f"Scraping properties... {properties_scraped:,} of {total_properties:,} properties scraped")
                
                if total_properties > 0:
                    progress_bar.progress(properties_scraped / total_properties)
                
                if current_page >= total_pages or not self.go_to_next_page():
                    break
                
                current_page += 1
            
            progress_bar.empty()
            status_text.empty()
            st.success(f"Successfully scraped {properties_scraped:,} of {total_properties:,} properties")
            
        except Exception as e:
            st.error(f"Error during extraction: {e}")
        
        return all_properties_data

    def apply_generic_filter(self, filter_attr, choice, mapping, filter_name):
        """Generic helper method to apply any filter on the website."""
        try:
            if choice not in mapping:
                st.error(f"Invalid {filter_name} choice: {choice}")
                return False
            
            filter_container = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f'div[attr="{filter_attr}"]'))
            )
            
            options = filter_container.find_elements(By.CSS_SELECTOR, '.ui.groupTop.horizontal.list.level0 a.item')
            
            for option in options:
                if option.get_attribute('data-value') == mapping[choice]:
                    option.click()
                    time.sleep(1)
                    return True
            
            st.error(f"Option with data-value '{mapping[choice]}' not found for {filter_name}")
            return False
        except Exception as e:
            st.error(f"Error applying {filter_name.title()} filter: {e}")
            return False

    def apply_property_type_filter(self, property_type):
        """Apply property type filter on website."""
        type_mapping = {
            "All": "0", "Apartment": "5", "Carpark": "6", 
            "Office": "7", "Shop": "8"
        }
        return self.apply_generic_filter("mainType", property_type, type_mapping, "Property Type")

    def apply_budget_filter(self, budget_choice):
        """Apply budget filter based on transaction type."""
        if self.transaction_type == "rent":
            budget_mapping = {
                "No preference": "0", "Below 10,000": "1", "10,000 - 20,000": "2",
                "20,000 - 40,000": "3", "40,000 - 60,000": "4", 
                "60,000 - 80,000": "5", "Above 80,000": "6"
            }
        else:
            budget_mapping = {
                "No preference": "0", "Below 10M": "1", "10M - 20M": "2",
                "20M - 40M": "3", "40M - 70M": "4", "70M - 100M": "5",
                "Above 100M": "6"
            }
        
        return self.apply_generic_filter("price", budget_choice, budget_mapping, 
                                       "Budget" if self.transaction_type == "rent" else "Price")

    def apply_area_filter(self, area_choice):
        """Apply area filter on website."""
        area_mapping = {
            "No preference": "0", "Below 300": "1", "300 - 500": "2",
            "500 - 1000": "3", "1000 - 2000": "4", "Above 2000": "5"
        }
        return self.apply_generic_filter("areaRange", area_choice, area_mapping, "Saleable Area")
        
    def apply_room_filter(self, room_choice):
        """Apply room filter on website."""
        room_mapping = {
            "No preference": "0", "Studio": "STUDIO", "1": "1",
            "2": "2", "3": "3", "4": "4", "5+": "5PLUS"
        }
        return self.apply_generic_filter("roomRange", room_choice, room_mapping, "Number of Rooms")
    
    def search_district(self, district):
        """Search for properties in the specified district."""
        try:
            search_input = self.wait.until(EC.element_to_be_clickable((By.NAME, 'searchText_temp')))
            search_input.clear()
            time.sleep(0.5)
            search_input.send_keys(district.title())
            
            search_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'searchwords_btn')))
            search_button.click()
            time.sleep(3)
            
            results_element = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[style*="float: left"]'))
            )
            results_text = results_element.text.strip()
            
            # Check for appropriate result text based on transaction type
            expected_text = "results of property for lease" if self.transaction_type == "rent" else "results of property for sale"
            
            if expected_text in results_text:
                num_str = results_text.split()[0].replace(',', '')
                return int(num_str) if num_str.isdigit() else 0
            return 0
        except Exception as e:
            st.error(f"Error searching district '{district.title()}': {e}")
            return 0
    
    def extract_property_name(self, header_element, district):
        """Extract individual property name."""
        try:
            full_text = header_element.text.strip()
            lines = full_text.split('\n')
            
            if lines:
                first_line = lines[0].strip()
                # Remove district if it's at the beginning
                return first_line[len(district):].strip() if first_line.startswith(district) else first_line
            return 'N/A'
        except Exception:
            return 'N/A'
    
    def extract_property_data(self, district):
        """Extract data from all property listings on the current page."""
        properties_data = []
        
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.property_item')))
            time.sleep(2)
            
            property_items = self.driver.find_elements(By.CSS_SELECTOR, 'div.item.property_item')
            
            for item in property_items:
                property_data = {'District': district, 'Name': 'N/A', 'Street Address': 'N/A',
                               self.price_field: 'N/A', 'Net Area (sqft)': 'N/A',
                               'Number of Bedrooms': 'N/A', 'Number of Bathrooms': 'N/A', 'URL': 'N/A'}
                
                try:
                    # Extract name
                    try:
                        header_cat = item.find_element(By.CSS_SELECTOR, 'div.header.cat')
                        property_data['Name'] = self.extract_property_name(header_cat, district)
                    except:
                        pass
                    
                    # Extract street address
                    try:
                        meta_divs = item.find_elements(By.CSS_SELECTOR, 'div.meta')
                        if meta_divs:
                            property_data['Street Address'] = meta_divs[0].text.strip()
                    except:
                        pass
                    
                    # Extract price
                    try:
                        price_element = item.find_element(By.CSS_SELECTOR, self.price_css_selector)
                        price_text = price_element.text.strip()
                        property_data[self.price_field] = self.extract_price_from_text(price_text)
                    except:
                        # Try alternative selector
                        try:
                            price_element = item.find_element(By.CSS_SELECTOR, 'span.priceDesc')
                            price_text = price_element.text.strip()
                            property_data[self.price_field] = self.extract_price_from_text(price_text)
                        except:
                            pass
                    
                    # Extract monthly repayment (buy only)
                    if self.transaction_type == "buy":
                        try:
                            meta_divs = item.find_elements(By.CSS_SELECTOR, 'div.meta')
                            for meta in meta_divs:
                                meta_text = meta.text.strip()
                                if 'monthly repayment:' in meta_text.lower():
                                    match = re.search(r'HKD\$([\d,]+)', meta_text)
                                    if match:
                                        property_data['Monthly Repayment (HKD)'] = match.group(1).replace(',', '')
                                    break
                        except:
                            property_data['Monthly Repayment (HKD)'] = 'N/A'
                    
                    # Extract area, bedrooms, bathrooms
                    try:
                        header_divs = item.find_elements(By.CSS_SELECTOR, 'div.header')
                        for header in header_divs:
                            text = header.text.strip()
                            if 'ft²' in text:
                                parts = text.split()
                                if len(parts) > 0:
                                    property_data['Net Area (sqft)'] = parts[0]
                                if len(parts) > 2:
                                    property_data['Number of Bedrooms'] = parts[2]
                                if len(parts) > 3:
                                    property_data['Number of Bathrooms'] = parts[3]
                                break
                    except:
                        pass
                    
                    # Extract URL
                    try:
                        img_element = item.find_element(By.CSS_SELECTOR, 'img.desktop_myimage.detail_page')
                        property_data['URL'] = img_element.get_attribute('href')
                    except:
                        pass
                    
                    properties_data.append(property_data)
                except Exception:
                    continue
                    
        except Exception as e:
            st.error(f"Error extracting property data: {e}")
        
        return properties_data
    
    def save_to_csv(self, properties_data):
        """Save extracted property data to a CSV file."""
        if not properties_data:
            return None
        
        try:
            # Define headers based on transaction type
            if self.transaction_type == "rent":
                headers = ["District", "Name", "Street Address", "Monthly Rental Price (in HKD)",
                          "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"]
            else:
                headers = ["District", "Name", "Street Address", "Sale Price (in HKD Millions)",
                          "Monthly Repayment (HKD)", "Net Area (sqft)", "Number of Bedrooms",
                          "Number of Bathrooms", "URL"]
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            for property_data in properties_data:
                property_data['District'] = property_data['District'].title()
                writer.writerow(property_data)
            
            return output.getvalue().encode('utf-8')
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
    ### Welcome to the *Hong Kong Property Scraper!*
    
    This tool helps you search and extract property data in Hong Kong for both **rental** and **sale** properties *(data retrieved from SquareFoot.com.hk)*. 
    Get started by navigating to the **Property Search** tab above.
    
    ---
    
    ## Quick Start Guide
    
    #### Step 1: Navigate to Property Search
    Click on the **"Property Search"** tab at the top of the page.
    
    #### Step 2: Select Transaction Type
    Choose between **Rent** or **Buy** properties.
    
    #### Step 3: Apply Filters (Optional)
    Use the filters in the search form to narrow down your search:
    - **Property Type**: Select from All, Apartment, Carpark, Office, or Shop
    - **Budget/Price Range**: Choose your preferred price range
    - **Saleable Area**: Filter by property size
    - **Number of Rooms**: Select bedroom requirements
    
    #### Step 4: Enter District
    - Type the relevant district you want to search for
    - Click the **"Search Properties"** button
    
    #### Step 5: Review Search Results
    - The app will show you how many properties were found
    
    #### Step 6: Extract Data
    - Click **"Extract Property Data"** to start scraping
    - A progress bar will show real-time progress
    
    #### Step 7: Download Your Data
    - Once extraction is complete, click the **"Download CSV"** button
    
    ---
    
    ## What Data Gets Extracted?
    
    - **District** - Your searched location
    - **Property Name** - Building/project name
    - **Street Address** - Full street address
    - **Price** - Monthly rent or sale price in HKD
    - **Monthly Repayment** (for buy properties only)
    - **Net Area** - Size in square feet
    - **Number of Bedrooms**
    - **Number of Bathrooms**
    - **Property URL** - Direct link to the listing
    
    ---
    
    *Happy Property Hunting!*
    """)

def show_property_search():
    """Display the property search interface"""
    
    # Initialize session state
    defaults = {
        'scraper': None, 'properties_data': None, 'search_performed': False,
        'extract_clicked': False, 'current_district': '', 'property_count': 0,
        'is_extracting': False, 'transaction_type': 'rent', 'property_type': 'All'
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Transaction Type Selection
    st.subheader("Transaction Type")
    transaction_type = st.radio(
        "Select transaction type:",
        ["Rent", "Buy"],
        horizontal=True,
        key="transaction_type_radio",
        on_change=lambda: st.session_state.update(
            search_performed=False, properties_data=None, extract_clicked=False
        )
    ).lower()
    
    # Update transaction type if changed
    if st.session_state.transaction_type != transaction_type:
        st.session_state.transaction_type = transaction_type
        st.session_state.update(search_performed=False, properties_data=None, extract_clicked=False)
    
    # Property Type Selection (outside the form for dynamic updates)
    st.subheader("Property Type")
    property_type = st.selectbox(
        "Select property type:",
        ["All", "Apartment", "Carpark", "Office", "Shop"],
        key="property_type_select"
    )
    
    # Store property type in session state
    st.session_state.property_type = property_type
    
    # Check if Carpark is selected to determine if we should disable other filters
    is_carpark = (property_type == "Carpark")
    
    if is_carpark:
        st.info("Note: Area and Room filters are not applicable for Carpark.")
    
    # Search form
    with st.form("search_form"):
        st.subheader("Search Filters")
        col1, col2 = st.columns(2)
        
        with col1:
            # Budget options based on transaction type
            if st.session_state.transaction_type == "rent":
                budget_options = ["No preference", "Below 10,000", "10,000 - 20,000",
                                "20,000 - 40,000", "40,000 - 60,000", "60,000 - 80,000",
                                "Above 80,000"]
                budget_label = "Monthly Budget (HKD)"
            else:
                budget_options = ["No preference", "Below 10M", "10M - 20M",
                                "20M - 40M", "40M - 70M", "70M - 100M", "Above 100M"]
                budget_label = "Price Range (HKD)"
            
            budget = st.selectbox(budget_label, budget_options)
        
        with col2:
            # Area filter - disabled if Carpark is selected
            area_options = ["No preference", "Below 300", "300 - 500", "500 - 1000",
                           "1000 - 2000", "Above 2000"]
            
            if is_carpark:
                area = st.selectbox(
                    "Saleable Area (sqft)",
                    area_options,
                    disabled=True,
                    help="Area filter is not available for Carpark properties"
                )
            else:
                area = st.selectbox(
                    "Saleable Area (sqft)",
                    area_options
                )
        
        # Second row for rooms (using full width or another column)
        if is_carpark:
            rooms = st.selectbox(
                "Number of Rooms",
                ["No preference", "Studio", "1", "2", "3", "4", "5+"],
                disabled=True,
                help="Room filter is not available for Carpark properties"
            )
        else:
            rooms = st.selectbox(
                "Number of Rooms",
                ["No preference", "Studio", "1", "2", "3", "4", "5+"]
            )
        
        district = st.text_input("District Name", help="e.g., Central, Causeway Bay, Tsim Sha Tsui")
        search_button = st.form_submit_button("Search Properties", type="primary", use_container_width=True)
    
    # Handle search
    if search_button and district:
        with st.spinner("Initializing scraper..."):
            if st.session_state.scraper:
                st.session_state.scraper.close()
                st.session_state.scraper = None
            
            try:
                scraper = PropertyScraper(st.session_state.transaction_type)
                
                # Apply filters
                scraper.apply_property_type_filter(property_type)
                scraper.apply_budget_filter(budget)
                
                # Only apply area and room filters if property type is not Carpark
                # Even if the user somehow manages to select values (though they're disabled), we still skip them
                if not is_carpark:
                    scraper.apply_area_filter(area)
                    scraper.apply_room_filter(rooms)
                
                property_count = scraper.search_district(district)
                
                if property_count > 0:
                    st.success(f"Found {property_count:,} properties")
                    st.session_state.update(
                        scraper=scraper, property_count=property_count,
                        current_district=district, search_performed=True,
                        extract_clicked=False, properties_data=None
                    )
                else:
                    st.warning("No properties found in this district")
                    st.session_state.search_performed = False
                    scraper.close()
            except Exception as e:
                st.error(f"Error during search: {e}")
                if st.session_state.scraper:
                    st.session_state.scraper.close()
                    st.session_state.scraper = None
    
    # Extract button
    if (st.session_state.search_performed and not st.session_state.extract_clicked and
        st.session_state.property_count > 0 and not st.session_state.is_extracting):
        
        if st.button("Extract Property Data", key="extract_button", use_container_width=True):
            st.session_state.is_extracting = True
            st.rerun()
    
    # Handle extraction
    if st.session_state.is_extracting and st.session_state.scraper:
        with st.spinner("Extracting property data... This may take a few minutes..."):
            st.session_state.properties_data = st.session_state.scraper.extract_all_property_data(
                st.session_state.current_district, st.session_state.property_count
            )
            st.session_state.update(extract_clicked=True, is_extracting=False)
            st.rerun()
    
    # Display results
    if st.session_state.properties_data:
        if len(st.session_state.properties_data) > 0:
            st.header("Search Results")
            df = pd.DataFrame(st.session_state.properties_data)
            
            # Define column order based on transaction type
            if st.session_state.transaction_type == "rent":
                column_order = [
                    "District", "Name", "Street Address", "Monthly Rental Price (in HKD)",
                    "Net Area (sqft)", "Number of Bedrooms", "Number of Bathrooms", "URL"
                ]
            else:  # buy
                column_order = [
                    "District", "Name", "Street Address", "Sale Price (in HKD Millions)",
                    "Monthly Repayment (HKD)", "Net Area (sqft)", "Number of Bedrooms",
                    "Number of Bathrooms", "URL"
                ]
            
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]
            
            st.dataframe(df, use_container_width=True)
            
            # Download button
            if st.session_state.scraper:
                csv_bytes = st.session_state.scraper.save_to_csv(st.session_state.properties_data)
                if csv_bytes:
                    prefix = "rental" if st.session_state.transaction_type == "rent" else "sale"
                    filename = f"{prefix}_property_data_{st.session_state.current_district}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv_bytes,
                        file_name=filename,
                        mime='text/csv',
                        use_container_width=True
                    )
            
            # Statistics
            st.header("Statistics")
            price_field = "Monthly Rental Price (in HKD)" if st.session_state.transaction_type == "rent" else "Sale Price (in HKD Millions)"
            
            # Calculate statistics
            prices = []
            for p in st.session_state.properties_data:
                price_str = p.get(price_field, 'N/A')
                if price_str != 'N/A':
                    try:
                        if st.session_state.transaction_type == "rent":
                            prices.append(int(price_str.replace(',', '')))
                        else:
                            prices.append(float(price_str))
                    except:
                        pass
            
            areas = []
            for p in st.session_state.properties_data:
                area_str = p.get('Net Area (sqft)', 'N/A')
                if area_str != 'N/A' and area_str.isdigit():
                    areas.append(int(area_str))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Properties", len(st.session_state.properties_data))
            with col2:
                if prices:
                    if st.session_state.transaction_type == "rent":
                        st.metric("Average Monthly Rent (HKD)", f"{sum(prices)//len(prices):,}")
                    else:
                        st.metric("Average Sale Price (HKD)", f"{sum(prices)/len(prices):.1f}M")
                else:
                    st.metric("Average Price", "N/A")
            with col3:
                if areas:
                    st.metric("Average Area (sqft)", f"{sum(areas)//len(areas)}")
                else:
                    st.metric("Average Area (sqft)", "N/A")
        else:
            st.info("No property data could be extracted.")
    elif st.session_state.search_performed and st.session_state.extract_clicked:
        st.info("No property data could be extracted.")

def main():
    st.set_page_config(page_title="Hong Kong Property Scraper")
    st.title("**Hong Kong Property Scraper**", text_alignment="center")
    
    tab1, tab2 = st.tabs(["Home", "Property Search"])
    with tab1:
        show_home_page()
    with tab2:
        show_property_search()
    
    # Cleanup
    def cleanup():
        if st.session_state.get('scraper'):
            st.session_state.scraper.close()
    
    atexit.register(cleanup)

if __name__ == "__main__":
    main()
