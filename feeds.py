import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from app.time import local_to_utc
import re

#from feedgen.feed import FeedGenerator

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0"
}

def string_to_dict(data, row_sep='\n', col_sep='=', key_type=str, value_type=str):
    return {
        key_type(pair.split(col_sep)[0].strip()): value_type(pair.split(col_sep)[1].strip())
        for pair in data.split(row_sep) if col_sep in pair
    }

def rename_dict_key(dict, key_name, new_key_name):
    if key_name in dict:
        dict[new_key_name] = dict.pop(key_name)

def data_keys_to_snake_case(data):
    if isinstance(data, dict):
        new_dict = data.__class__() # Preserve original dict type (e.g., OrderedDict)
        for old_key, value in data.items():
            new_key = camel_to_snake(old_key)
            new_dict[new_key] = data_keys_to_snake_case(value)
        return new_dict
    elif isinstance(data, list):
        return [data_keys_to_snake_case(item) for item in data]
    else:
        return data  

def camel_to_snake(name):
    # Insert an underscore before any uppercase character that follows a lowercase character or digit
    s1 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    # Convert the entire string to lowercase
    return s1.lower()

class Openlands:
    #TODO - check if there exists an img tag with src similar to the below (just org_id and event_id should be sufficient). This is the event image (doesn't always exist)
    #https://cdn.cervistech.com/acts/module/display_event_photo.php?event_id=2820&org_id=0254&ver=b6f6f4cca95e93394bacf9f2f229cd39d24b9efe0689988b156be38ed5a9ccc9

    url = 'https://www.cervistech.com/acts/webreg/eventwebreglist.php?org_id=0254'

    @staticmethod
    def getEventDetails(eventId):
        # print("eventId: ", eventId)
        details = {'event_id': eventId}
        event = requests.get(f'https://www.cervistech.com/acts/webreg/eventdetail.php?event_id={eventId}&org_id=0254&hide_buttons=yes&back=min',headers=headers)
        soup = BeautifulSoup(event.content, "html.parser")
        slots = []

        try:
            text = "Opportunity Name:"
            element = soup.find(lambda tag: tag.name == "td" and text in tag.text)
            details['opportunity_name'] = element.get_text().replace(text,"").strip()
        except:
            element

        try:
            text = "Description:"
            element = soup.find(lambda tag: tag.name == "td" and text in tag.text)
            details['description'] = element.get_text().replace(text,"").strip()
        except:
            element

        try:
            text = "Date/Time:"
            element = soup.find(lambda tag: tag.name == "tr" and text in tag.text)
            tempVal = element.get_text().replace(text,"").strip()         #	Tue, May 20, 2025 - 7:30 PM to 8:30 PM
            slot = Openlands.parseEventTime(tempVal)

            text = "Spots Available:"
            element = soup.find(lambda tag: tag.name == "tr" and text in tag.text)
            tempVal = element.get_text().replace(text,"").strip()
            slot['spots_available'] = Openlands.parseSlotsAvailable(tempVal)

            slots.append(slot)
        except:
            element

        try:
            text = "Meeting Location:"
            element = soup.find(lambda tag: tag.name == "tr" and text in tag.text)
            details['meeting_location_desc'] = element.get_text().replace(text,"").replace("View Map / Get Directions","").strip()
            details['meeting_location'] = element.find("a")["href"]
        except:
            element

        try:
            text = "Organizer:"
            element = soup.find(lambda tag: tag.name == "tr" and text in tag.text)
            details['organizer'] = Openlands.parseOrganizer(element) # element.get_text().replace(text,"") #.strip()
        except:
            element

        try:
            text = "Category:"
            element = soup.find(lambda tag: tag.name == "tr" and text in tag.text)
            #print(element.get_text())
            details['category'] = element.get_text().replace(text,"").strip()
        except:
            element

        #timeslots (doesn't always exist) 2596, 2591, 2503 
        slots = [*slots, *Openlands.extractSlotsTable(soup.find('table', id='result_list'))]
        details['slots'] = slots

        details['url'] =  f"https://www.cervistech.com/acts/webreg/eventdetail.php?event_id={eventId}&org_id=0254" #&hide_buttons=yes&back=min"

        event_time = Openlands.establishEventTime(slots)
        if not event_time is None:
            details = {**details, **event_time}
            # details['startTime'] = event_time['startTime']
            # details['endTime'] = event_time['endTime']
            return details
        else:
            return None
        
    @staticmethod
    def establishEventTime(slots):
        #establish event level start/end time
        eventTime = {}
        startTime = None
        endTime = None

        if len(slots) >= 1:
            for slot in slots:
                slotStartTime = datetime.fromisoformat(slot['start_time'])
                if startTime is None or slotStartTime < startTime:
                    startTime = slotStartTime
                slotEndTime = datetime.fromisoformat(slot['end_time'])
                if endTime is None or slotEndTime > endTime:
                    endTime = slotEndTime
            eventTime['start_time'] = startTime.isoformat()
            eventTime['end_time'] = endTime.isoformat()
            return eventTime
        else:
            return None

    @staticmethod
    def parseEventTime(text):
        retDict = {}
        text = text.replace("\xa0"," ").strip()
        eventDate = text.split(" - ")[0]
        startTime = text.split(" - ")[1].split(" to ")[0]
        endTime = text.split(" - ")[1].split(" to ")[1]
        retDict['start_time'] = local_to_utc(datetime.strptime(eventDate + " " + startTime, "%a, %b %d, %Y %I:%M %p"), "America/Chicago").isoformat()
        retDict['end_time'] = local_to_utc(datetime.strptime(eventDate + " " +  endTime, "%a, %b %d, %Y %I:%M %p"), "America/Chicago").isoformat()
        return retDict

    @staticmethod
    def parseSlotsAvailable(text):
        retval = ''
        parse = BeautifulSoup(text,"html.parser").get_text()
        if parse == 'Unlimited':
            retval = 99
        elif parse == 'Waitlist':
            retval = -1
        elif parse == 'Event Full':
            retval = 0
        else:
            retval = parse
        return retval

    @staticmethod
    def parseOrganizer(element):
        child = element.find_all("td")[1]
        retDict = {}
        retDict["organizer_name"] = child.contents[0]
        retDict["organizer_email"] = child.contents[2]
        try:
            if "/" in child.contents[4]:
                retDict["organizer_phone"] = child.contents[4].split(' / ')
            else:
                retDict["organizer_phone"] = [child.contents[4]]
        except:
            retDict["organizer_phone"] = []
        return retDict

    @staticmethod
    def extractSlotsTable(table):
        # alternative method: https://stackoverflow.com/a/51657193
        slots = []
        if table:
            rows = table.find_all("tr", class_="over")
            for row in rows:
                children = row.find_all("td")
                #first td has startTime, endTime, and activityName separated from the first two by a <br>
                slot = {}
                slot = Openlands.parseEventTime(children[0].contents[0])
                #slot["dateTime"] = parseEventTime(children[0].contents[0])
                try:
                    slot["activity"] = children[0].contents[2] #not always an activity present
                except:
                    slot["activity"] = ""
                slotInfo = row['title'].replace("header=[Slot Information] body=","").replace("[","").replace("]","")
                slotInfos = string_to_dict(slotInfo, "<br />", ":")
                slotInfos = {key.replace(" ",""): value for key, value in slotInfos.items()}
                # rename_dict_key(slotInfos, "NumberCurrentlyonWaitlist", "number_currently_on_waitlist")
                # rename_dict_key(slotInfos, "NumberRegistered", "number_registered")
                # rename_dict_key(slotInfos, "ServiceHours", "service_hours")
                # rename_dict_key(slotInfos, "SpotsAvailable", "spots_available")
                # rename_dict_key(slotInfos, "TotalNeeded", "total_needed")
                slotInfos["SpotsAvailable"] = Openlands.parseSlotsAvailable(slotInfos["SpotsAvailable"])
                slot = {**slot, **slotInfos}
                slots.append(slot)
        #print(slots)
        return slots
    
    @staticmethod
    def get(destination="feed"):
        response = requests.get(Openlands.url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Check the status code
        #print(f"Status Code: {response.status_code}")

        links = soup.find_all('a')
        raw_events = []

        for link in links:
            if 'event_id' in link['href']:
                parsed = urlparse(link['href'])
                id = parse_qs(parsed.query)['event_id'][0]
                raw_event = Openlands.getEventDetails(id)

                #if event has an event time
                if not raw_event is None:
                    raw_events.append(raw_event)

        #reusable methods (but not in reusable class yet)
        data_keys_to_snake_case(raw_events)

        #send whole bridge or convert to feed for ingestion into event model
        if destination == "feed":
            field_map = {
                "opportunity_name": "title",
                "start_time": "starts_at",
                "end_time": "ends_at",
                "meeting_location": "location",
                "meeting_location_desc": "location_desc",
                "event_id": "original_event_id",
                "url": "original_event_url",
                "category": "original_event_category",
            }
            events = []
            for raw_event in raw_events:
                raw_event.pop('slots')
                raw_event.pop('organizer')
                event = {field_map.get(k, k): v for k, v in raw_event.items()}
                events.append(event)
            return events
        elif destination == "bridge":
            return raw_events

# def create_feed():
#     fg = FeedGenerator()
#     fg.title('My Awesome Blog')
#     fg.description('The latest updates from my blog.')
#     fg.link(href='http://localhost:5000/rss', rel='self') # Link to the feed itself
#     fg.link(href='http://localhost:5000/', rel='alternate') # Link to your website

#     # Example blog posts (you would typically fetch these from a database)
#     posts = [
#         {'title': 'First Post', 'link': 'http://localhost:5000/post/1', 'description': 'This is the first post.', 'pubDate': datetime(2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc)},
#         {'title': 'Second Post', 'link': 'http://localhost:5000/post/2', 'description': 'This is the second post.', 'pubDate': datetime(2023, 10, 27, 11, 30, 0, tzinfo=timezone.utc)},
#     ]

#     for post in posts:
#         fe = fg.add_entry()
#         fe.title(post['title'])
#         fe.link(href=post['link'])
#         fe.description(post['description'])
#         fe.pubDate(post['pubDate'])

#     # Generate the RSS XML string
#     return fg.rss_str(pretty=True)

# Print the response content
#print(f"Content: {response.text}")
if __name__ == "__main__":
    print(Openlands.get())
    #print(create_feed())