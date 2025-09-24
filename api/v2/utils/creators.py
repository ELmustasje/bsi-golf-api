async def create_member_dict(s, group_id):
    group = await s.get_group(group_id)
    members = {}
    for member in group["members"]:
        id = member["id"]
        name = member["firstName"] + " " + member["lastName"]
        members[id] = name
    return members
