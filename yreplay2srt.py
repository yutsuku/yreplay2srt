#!/usr/bin/python

import pysrt
import json
import sys
import functools
import copy
from urllib import request
import re


class LiveChat():
    def __init__(self, livechatJson, modOnly, max_comments_view_len=160, max_comments_per_view=4):
        self.livechatJson = livechatJson
        self.modOnly = modOnly
        self.max_comments_view_len = max_comments_view_len
        self.max_comments_per_view = max_comments_per_view

    def live_chat_to_srt(self):
        comments = []
        j_content = None

        with open(self.livechatJson) as f:
            chat_chunk = None
            for line in f:
                try:
                    chat_chunk = json.loads(line)
                except Exception as e:
                    print(e)
                    continue
                comments += parse_comments(chat_chunk, self.modOnly)
                comments += parse_paid_comments(chat_chunk, self.modOnly)

        comments = functools.reduce(uniq_comments, comments, [])
        subs = comments_to_subs(comments, max_comments_view_len=self.max_comments_view_len, max_comments_per_view=self.max_comments_per_view)
        return pysrt.SubRipFile(subs)


def json_file_key(name):
    a = name.index('.')
    return int(name[:a])

class Date():
    def __init__(self, sec, minute, hour=0, msec=0):
        self.hour = hour
        self.minute = minute
        self.sec = sec
        self.msec = 0
    
    def to_seconds(self):
        return (self.hour * 60 * 60) + (self.minute *  60) + self.sec
    
    def add_seconds(self, value):
        self.sec = self.sec + value

        if self.sec > 59:
            self.sec = 0
            self.minute = self.minute + 1
        
        if self.minute > 59:
            self.minute = 0
            self.hour = self.hour + 1
        
        return self

    def __eq__(self, other):
        return self.hour == other.hour and self.minute == other.minute and self.sec == other.sec and self.msec == other.msec

    def __gt__(self, other):
        if self.hour != other.hour and self.hour < other.hour:
            return False
        elif self.minute != other.minute and self.minute < other.minute:
            return False
        elif self.sec != other.sec and self.sec < other.sec:
            return False
        elif self.msec != other.msec and self.msec < other.msec:
            return False
        elif self != other:
            return True

        return False

class Comment():
    def __init__(self, author, date, text, isModer=False, paidAmount=None):
        self.author = author
        self.date = date
        self.text = text
        self.isModer = isModer
        self.paidAmount = paidAmount
        if paidAmount:
            print(author, text)


def parse_comments(js_com, modOnly=False):
    act = js_com
    comments = []
    try:
        value = act['replayChatItemAction']['actions'][0]['addChatItemAction']['item']['liveChatTextMessageRenderer']
    except:
        return comments

    isModer = False
    text = ''
    try:
        nodes = value['message']['runs']
        for i, node in enumerate(nodes):
            if 'text' in node:
                text += node['text']
    except:
        pass
    author = value['authorName']['simpleText']
    try:
        isModer = value['authorBadges'][0]['liveChatAuthorBadgeRenderer']['icon']['iconType'] == "MODERATOR"
    except Exception as e:
        isModer = False
    date_raw = value['timestampText']['simpleText']
    hms = date_raw.split(':')
    date = None
    if len(hms) == 2:
        m, s = hms
        date = Date(int(s), int(m))
    elif len(hms) == 3:
        h, m, s = hms
        date = Date(int(s), int(m), int(h))
    else:
        raise Exception("date array wrong")

    if text:
        if modOnly:
            if isModer:
                comments.append(Comment(author, date, text, isModer))
        else:
            comments.append(Comment(author, date, text, isModer))

    return comments
    
def parse_paid_comments(js_com, modOnly=False):
    act = js_com
    comments = []
    try:
        value = act['replayChatItemAction']['actions'][0]['addChatItemAction']['item']['liveChatPaidMessageRenderer']
    except:
        return comments

    isModer = False
    text = ''
    amount = None
    try:
        amount = value['purchaseAmountText']['simpleText']
    except:
        pass
    try:
        nodes = value['message']['runs']
        for i, node in enumerate(nodes):
            if 'text' in node:
                text += node['text']
    except:
        pass
    author = value['authorName']['simpleText']
    try:
        isModer = value['authorBadges'][0]['liveChatAuthorBadgeRenderer']['icon']['iconType'] == "MODERATOR"
    except Exception as e:
        isModer = False
    date_raw = value['timestampText']['simpleText']
    hms = date_raw.split(':')
    date = None
    if len(hms) == 2:
        m, s = hms
        date = Date(int(s), int(m))
    elif len(hms) == 3:
        h, m, s = hms
        date = Date(int(s), int(m), int(h))
    else:
        raise Exception("date array wrong")

    if text:
        if modOnly:
            if isModer:
                comments.append(Comment(author, date, text, isModer, amount))
        else:
            comments.append(Comment(author, date, text, isModer, amount))

    return comments

def uniq_comments(old, new):
    for i in old:
        if i.author == new.author and i.date == new.date and i.text == new.text:
            return old

    old.append(new)
    return old

def comments_to_subs(comments, max_comments_view_len=160, max_comments_per_view=4, reverse=False):
    subrip_items = []
    item_comments = []
    item_index = 0
    
    max_duration = 10
    duration_multiplier = 3000
    
    color_moderator = "5f84f1"
    color_member = None
    color_user = "ffffff"
    color = None

    # fix time due to some comments can have same time with next comment
    for z, c in enumerate(comments):
        if len(comments) == z+1:
            continue
        if comments[z].date == comments[z + 1].date:
            comments[z + 1].date.msec += 500
        # if comments[z].date > comments[z + 1].date:
        #     comments[z + 1].date.msec = 500
        if len(comments) == z + 2:
            continue
        if comments[z+1].date > comments[z + 2].date:
            comments[z + 2].date.msec += 500

    for i, com in enumerate(comments):
        color = color_user
        if com.isModer:
            color = color_moderator
            
        msg_part_1 = '<font color="{0}">{1}</font>'.format(color, com.author)
        msg_part_2 = ': '
        
        msg_part_3 = ''
        if com.paidAmount:
            msg_part_3 = '<font color="{0}">[{1}]</font>'.format(color, com.paidAmount)

        msg_part_4 = com.text
        
        msg_line = msg_part_1 + msg_part_2 + msg_part_3 + msg_part_4
        
        if reverse:
            item_comments = [msg_line] + item_comments
        else:
            item_comments.append(msg_line)

        if len(item_comments) > max_comments_per_view:
            item_comments = item_comments[:max_comments_per_view] if reverse else item_comments[max(0, len(item_comments) - max_comments_per_view):]
        if len('\n'.join(item_comments)) >= max_comments_view_len:
            item_comments = item_comments[:3] if reverse else item_comments[max(0, len(item_comments) - 3):]

        #if len(comments) > i+1 and com.date > comments[i+1].date:
        #    raise Exception('wrong time range ', i)
        
        #local last_msg_offset = comments[#comments].content_offset_seconds
        #local segment_duration = last_msg_offset - comments[1].content_offset_seconds
        #local per_msg_duration = math.min(segment_duration * o.duration_multiplier / #comments, o.max_duration)
        
        message_time_to = None
        last_msg_offset = comments[i-1].date.to_seconds()
        
        if len(comments) > i+1:
            message_time_to = comments[i+1].date
            segment_duration = comments[i+1].date.to_seconds() - last_msg_offset
        else:
            message_time_to = com.date
            segment_duration = comments[i].date.to_seconds() - last_msg_offset
            
        
        
        per_msg_duration = min(segment_duration * duration_multiplier / len(comments), max_duration)
        
        message_time_to = copy.copy(com.date)
        message_time_to = message_time_to.add_seconds(per_msg_duration)

        #if message_time_to.to_seconds() - com.date.to_seconds() > max_duration:
        #    message_time_to = copy.copy(com.date)
        #    message_time_to = message_time_to.add_seconds(max_duration)

        start_time = pysrt.SubRipTime(com.date.hour,
                                      com.date.minute,
                                      com.date.sec,
                                      com.date.msec)
        end_time = pysrt.SubRipTime(message_time_to.hour,
                                    message_time_to.minute,
                                    message_time_to.sec,
                                    message_time_to.msec)
        subitem = pysrt.SubRipItem(item_index,
                                   start_time,
                                   end_time,
                                   '\n'.join(item_comments))
        subrip_items.append(subitem)
        item_index += 1

    return subrip_items


def main(livechatJson, path=None, modOnly=False):
    # dir = os.listdir(path)
    # path = os.path.normpath(path)
    # dir.sort(key=json_file_key)
    # comments = []
    # for f in dir:
    #     jf = open(path+f, 'r')
    #     js_com = json.loads(jf.read())
    #     comments += parse_comments(js_com)
    # comments = functools.reduce(uniq_comments, comments, [])
    # subs = comments_to_subs(comments)
    # pysrt.SubRipFile(subs).save(sys.argv[2])
    lc = LiveChat(livechatJson, modOnly, max_comments_per_view=1)
    lc.live_chat_to_srt().save(path)

def print_usage():
    print('''Usage:
yreplay2srt.py livechat.json [modOnly]
''')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(-1)

    output = r"{path}.srt".format(path=(sys.argv[1]))
    
    if len(sys.argv) == 3:
       main(sys.argv[1], output, sys.argv[3])
    else:
       main(sys.argv[1], output, False)
    
