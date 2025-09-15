import asyncio
import datetime
import re
from spond import spond

username = "+4748456975"
password = "TB-bt1a@"
group_id = "8D0C460783EB466B98AF0C3980163A34"


async def main():
    s = spond.Spond(username=username, password=password)
    group = await s.get_group(group_id)
    events = await s.get_events([group_id])

    print(events[0].keys())
    for event in events:
        if "Trening" in event["heading"]:
            print(event["heading"])
    # print(group.keys())
    # print(group["activity"])
    await s.clientsession.close()


def extract_feuture_trainings(events):
    trainings = []
    now = datetime.datetime.now()
    threshold = now + datetime.timedelta(hours=12)
    for event in events:
        endTimeStamp = event["endTimestamp"]
        if "Trening" in event["heading"] and endTimeStamp > threshold:
            trainings.append(event)

    return trainings


asyncio.run(main())
