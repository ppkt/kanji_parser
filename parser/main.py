# -*- coding: utf-8 -*-
import re
from auth import *

class Entry:
    def __init__(self):
        self.japanese = ''
        self.polish = ''
        self.meanings = []
        self.constructions = []


    def __unicode__(self):
        a = 'Entry\n'
        a+= self.japanese + '\n'
        a+= self.polish + '\n'
        i = 1
        for meaning in self.meanings:
            a += '%d %s\n' % (i, meaning)
            i += 1
        i = 1
        for construction in self.constructions:
            a += '%d %s\n' % (i, construction)
            i += 1
        return a + '\n'

def parse_content(file):
    starts_with_digit = re.compile('^\d+(.*)', re.UNICODE)
    state = 1
    current_entry = Entry()

    consume = True
    idx = 0

    lines = file.split('\n')

    while True:
        # Weird construction because python does not have 'repeat' keyword
        if consume:
            idx += 1
            line = lines.pop(0)
            line = unicode(line.strip(), 'utf-8')
            if len(line) == 0:
                continue
        consume = True

        # Polish - Japanese translation
        if state == 1:
            splitted = line.split('-', 1)
            if len(splitted) != 2:
                print 'Gordon, something is borken'
                print idx, line
                splitted = line.split(' ', 1)
            current_entry.japanese = splitted[0].strip()
            current_entry.polish = splitted[1].strip()
            state += 1
        # Examples
        elif state == 2:
            match = starts_with_digit.match(line)
            if match:
                current_entry.meanings.append(match.group(1)[1:])
            else:
                state += 1
                consume = False
        # Constructions
        elif state == 3:
            if line.startswith(u"K:"):
                current_entry.constructions = line[2:].split(u'｜')
            else:
                consume = False

            state = 1
            yield current_entry
            current_entry = Entry()


def main():
    gdrive = GoogleDriveAuth()
    #username = raw_input("Username: ")
    username = 'ppkt'

    credentials = gdrive.get_stored_credentials(username)

    # Credentials not found in file
    if not credentials:
        print 'Open link below in web browser and log in'
        print gdrive.get_authorization_url(username, '1')
        auth_code = raw_input("Write authorisation code from url: ")
        credentials = gdrive.exchange_code(auth_code)
        gdrive.store_credentials(username, credentials)
    # Use existing credentials
    else:
        print 'User authorised automagically'

    google_drive_service = gdrive.build_service(credentials)

    dokument = '1t2UjR9_Trc4jlFsCIN_gvUaFrnsxRBfdmxKmcbUER64'
    kanji = '1XCGpo3EoGE7xrYJm2wTCd_Et0GkiCmD05_Mxvyho8xE'

    gdrive.print_file_metadata(google_drive_service, kanji)
    file_content = gdrive.download_file(google_drive_service, kanji)

    for result in parse_content(file_content):
        #python and unicode...
        print u'%s' % result

    #print gdrive.retrieve_all_files(google_drive_service)

if __name__ == '__main__':
    main()