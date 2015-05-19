# Copyright (C) 2003 - 2007 The Board of Regents of the University of Wisconsin System 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

"""This module implements the Clip class as part of the Data Objects."""

__author__ = 'Nathaniel Case, David Woods <dwoods@wcer.wisc.edu>'

DEBUG = False
if DEBUG:
    print "Clip DEBUG is ON!"

import wx
from DataObject import *
from DBInterface import *
from TransanaExceptions import *
import Episode
import ClipKeywordObject
import Collection
import Transcript
import Note
# Import the Transana Constants
import TransanaConstants
# Import Transana's Global Variables
import TransanaGlobal
import types

TIMECODE_CHAR = "\\'a4"   # Note that this differs from the TIMECODE_CHAR in TranscriptEditor.py
                          # because this is for RTF text and that is for parsed text.

class Clip(DataObject):
    """This class defines the structure for a clip object.  A clip object
    describes a portion of a video (or other media) file."""

    def __init__(self, id_or_num=None, collection_name=None, collection_parent=0):
        """Initialize an Clip object."""
        DataObject.__init__(self)
        # By default, use the Video Root folder if one has been defined
        self.useVideoRoot = (TransanaGlobal.configData.videoPath != '')

        if type(id_or_num) in (int, long):
            self.db_load_by_num(id_or_num)
        elif isinstance(id_or_num, types.StringTypes):
            self.db_load_by_name(id_or_num, collection_name, collection_parent)
        else:
            self.number = 0
            self.id = ''
            self.comment = ''
            self.collection_num = 0
            self.collection_id = ''
            self.episode_num = 0
            # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
            self.transcript_num = 0
            self.clip_transcript_num = 0
            self.media_filename = 0
            self.clip_start = 0
            self.clip_stop = 0
            self.sort_order = 0
            
        # Create empty placeholders for Series and Episode IDs.  These only get populated if the
        # values are needed, and cannot be implemented in the regular LOADs because the Series/
        # Episode may no longer exist.
        self._series_id = ""
        self._episode_id = ""


# Public methods
    def __repr__(self):
        str = 'Clip Object Definition:\n'
        str = str + "number = %s\n" % self.number
        str = str + "id = %s\n" % self.id
        str = str + "comment = %s\n" % self.comment
        str = str + "collection_num = %s\n" % self.collection_num 
        str = str + "collection_id = %s\n" % self.collection_id
        str = str + "episode_num = %s\n" % self.episode_num
        # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
        str = str + "Originating transcript_num = %s\n" % self.transcript_num
        str = str + "clip_transcript_num = %s\n" % self.clip_transcript_num
        str = str + "media_filename = %s\n" % self.media_filename 
        str = str + "clip_start = %s\n" % self.clip_start
        str = str + "clip_stop = %s\n" % self.clip_stop
        str = str + "sort_order = %s\n" % self.sort_order
        for kws in self.keyword_list:
            str = str + "Keyword:  %s\n" % kws
        str = str + '\n'
        return str
        
    def GetTranscriptWithoutTimeCodes(self):
        """ Returns a copy of the Transcript Text with the Time Code information removed. """
        newText = self.text
        while True:
            timeCodeStart = newText.find(TIMECODE_CHAR)
            if timeCodeStart == -1:
                break
            timeCodeEnd = newText.find('>', timeCodeStart)

            newText = newText[:timeCodeStart] + newText[timeCodeEnd + 1:]

        # We should also replace TAB characters with spaces        
        while True:
            tabStart = newText.find(chr(wx.WXK_TAB), 0)
            if tabStart == -1:
                break
            newText = newText[:tabStart] + '  ' + newText[tabStart + 1:]

        return newText

    def db_load_by_name(self, clip_name, collection_name, collection_parent=0):
        """Load a record by ID / Name."""
        # If we're in Unicode mode, we need to encode the parameter so that the query will work right.
        if 'unicode' in wx.PlatformInfo:
            clip_name = clip_name.encode(TransanaGlobal.encoding)
            collection_name = collection_name.encode(TransanaGlobal.encoding)
        db = DBInterface.get_db()
        query = """
        SELECT a.*, b.*, c.TranscriptNum ClipTranscriptNum, c.RTFText
          FROM Clips2 a, Collections2 b, Transcripts2 c
          WHERE ClipID = %s AND
                a.CollectNum = b.CollectNum AND
                b.CollectID = %s AND
                b.ParentCollectNum = %s AND
                c.TranscriptID = "" AND
                a.ClipNum = c.ClipNum
        """
        c = db.cursor()
        c.execute(query, (clip_name, collection_name, collection_parent))
        n = c.rowcount
        if (n != 1):
            c.close()
            self.clear()
            raise RecordNotFoundError, (collection_name + ", " + clip_name, n)
        else:
            r = DBInterface.fetch_named(c)
            self._load_row(r)
            self.refresh_keywords()
            
        c.close()
        
    def db_load_by_num(self, num):
        """Load a record by record number."""
        db = DBInterface.get_db()
        query = """
        SELECT a.*, b.*, c.TranscriptNum ClipTranscriptNum, c.RTFText
          FROM Clips2 a, Collections2 b, Transcripts2 c
          WHERE a.ClipNum = %s AND
                a.CollectNum = b.CollectNum AND
                c.TranscriptID = "" AND
                a.ClipNum = c.ClipNum
        """
        c = db.cursor()
        c.execute(query, (num,))
        n = c.rowcount
        if (n != 1):
            c.close()
            self.clear()
            raise RecordNotFoundError, (num, n)
        else:
            r = DBInterface.fetch_named(c)
            self._load_row(r)
            self.refresh_keywords()

        c.close()

    def db_save(self):
        """Save the record to the database using Insert or Update as
        appropriate."""
        # Sanity checks
        if self.id == "":
            raise SaveError, _("Clip ID is required.")
        if (self.collection_num == 0):
            raise SaveError, _("Parent Collection number is required.")
        # If the transcript that a Clip was created from is deleted, you can have a Clip without a Transcript Number.
        # Legacy Data may also have no Transcript Number.
        # elif (self.transcript_num == 0):
            # raise SaveError, "No Transcript number"
        elif self.media_filename == "":
            raise SaveError, _("Media Filename is required.")
        # If a user Adjusts Indexes, it's possible to have a clip that starts BEFORE the media file.
        elif self.clip_start < 0.0:
            raise SaveError, _("Clip cannot start before media file begins.")
        else:
            # videoPath probably has the OS.sep character, but we need the generic "/" character here.
            videoPath = TransanaGlobal.configData.videoPath.replace('\\', '/')
            # Determine if we are supposed to extract the Video Root Path from the Media Filename and extract it if appropriate
            if self.useVideoRoot and (videoPath == self.media_filename[:len(videoPath)]):
                tempMediaFilename = self.media_filename[len(videoPath):]
            else:
                tempMediaFilename = self.media_filename

            # Substitute the generic OS seperator "/" for the Windows "\".
            self.media_filename = self.media_filename.replace('\\', '/')
            # If we are using the ANSI version of wxPython OR
            # (if we're on the Mac AND are in the Single-User version of Transana)
            # then we need to block Unicode characters from media filenames.
            # Unicode characters still cause problems on the Mac for the Multi-User version of Transana,
            # but can be made to work if shared waveforming is done on a Windows computer.
            if ('ansi' in wx.PlatformInfo) or (('wxMac' in wx.PlatformInfo) and TransanaConstants.singleUserVersion):
                # Create a string of legal characters for the file names
                allowedChars = TransanaConstants.legalFilenameCharacters
                # check each character in the file name string
                for char in self.media_filename:
                    # If the character is illegal ...
                    if allowedChars.find(char) == -1:
                        if 'unicode' in wx.PlatformInfo:
                            # Encode with UTF-8 rather than TransanaGlobal.encoding because this is a prompt, not DB Data.
                            msg = unicode(_('There is an unsupported character in the Media File Name.\n\n"%s" includes the "%s" character, \nwhich Transana on the Mac does not support at this time.  Please rename your folders \nand files so that they do not include characters that are not part of English.'), 'utf8') % (self.media_filename, char)
                        else:
                            msg = _('There is an unsupported character in the Media File Name.\n\n"%s" includes the "%s" character, \nwhich Transana on the Mac does not support at this time.  Please rename your folders \nand files so that they do not include characters that are not part of English.') % (self.media_filename, char)
                        raise SaveError, msg
            # If we're not in Unicode mode ...
            if 'ansi' in wx.PlatformInfo:
                # ... we don't need to encode the string values, but we still need to copy them to our local variables.
                id = self.id
                comment = self.comment
            # If we're in Unicode mode ...
            else:
                # Encode strings to UTF8 before saving them.  The easiest way to handle this is to create local
                # variables for the data.  We don't want to change the underlying object values.  Also, this way,
                # we can continue to use the Unicode objects where we need the non-encoded version. (error messages.)
                id = self.id.encode(TransanaGlobal.encoding)
                tempMediaFilename = tempMediaFilename.encode(TransanaGlobal.encoding)
                videoPath = videoPath.encode(TransanaGlobal.encoding)
                comment = self.comment.encode(TransanaGlobal.encoding)

        self._sync_collection()

        values = (id, self.collection_num, self.episode_num, \
                      self.transcript_num, tempMediaFilename, \
                      self.clip_start, self.clip_stop, comment, \
                      self.sort_order)
        if (self._db_start_save() == 0):
            if DBInterface.record_match_count("Clips2", \
                                ("ClipID", "CollectNum"), \
                                (id, self.collection_num) ) > 0:
                if 'unicode' in wx.PlatformInfo:
                    # Encode with UTF-8 rather than TransanaGlobal.encoding because this is a prompt, not DB Data.
                    prompt = unicode(_('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.'), 'utf8') % self.id
                else:
                    prompt = _('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.') % self.id
                raise SaveError, prompt
            # insert the new record
            query = """
            INSERT INTO Clips2
                (ClipID, CollectNum, EpisodeNum, TranscriptNum,
                 MediaFile, ClipStart, ClipStop, ClipComment,
                 SortOrder)
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
        else:
            if DBInterface.record_match_count("Clips2", \
                            ("ClipID", "CollectNum", "!ClipNum"), \
                            (id, self.collection_num, self.number)) > 0:
                if 'unicode' in wx.PlatformInfo:
                    # Encode with UTF-8 rather than TransanaGlobal.encoding because this is a prompt, not DB Data.
                    prompt = unicode(_('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.'), 'utf8') % self.id
                else:
                    prompt = _('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.') % self.id
                raise SaveError, prompt

            # update the record
            query = """
            UPDATE Clips2
                SET ClipID = %s,
                    CollectNum = %s,
                    EpisodeNum = %s,
                    TranscriptNum = %s,
                    MediaFile = %s,
                    ClipStart = %s,
                    ClipStop = %s,
                    ClipComment = %s,
                    SortOrder = %s
                WHERE ClipNum = %s
            """
            values = values + (self.number,)
        
        c = DBInterface.get_db().cursor()
        c.execute(query, values)
        if self.number == 0:
            # If we are dealing with a brand new Clip, it does not yet know its
            # record number.  It HAS a record number, but it is not known yet.
            # The following query should produce the correct record number.
            query = """
                      SELECT ClipNum FROM Clips2
                      WHERE ClipID = %s AND
                            CollectNum = %s
                    """
            tempDBCursor = DBInterface.get_db().cursor()
            tempDBCursor.execute(query, (id, self.collection_num))
            if tempDBCursor.rowcount == 1:
                self.number = tempDBCursor.fetchone()[0]
            else:
                raise RecordNotFoundError, (self.id, tempDBCursor.rowcount)
            tempDBCursor.close()
        else:
            # If we are dealing with an existing Clip, delete all the Keywords
            # in anticipation of putting them all back in after we deal with the
            # Clip Transcript
            DBInterface.delete_all_keywords_for_a_group(0, self.number)
        # Now let's deal with the Clip's Transcript
        if self.clip_transcript_num == 0:
            # Create a Transcript Object for the Transcript data
            tempTranscript = Transcript.Transcript()
            # Assign the data that needs to be saved
            tempTranscript.episode_num = self.episode_num
            tempTranscript.clip_num = self.number
            tempTranscript.text = self.text
            # Save the new Transcript record
            tempTranscript.db_save()
            # Now we need to assign the Transcript Object's new Record Number to the
            # Clip Object.  First, let's reload the Transcript Object so it knows it's
            # record number
            tempTranscript = Transcript.Transcript(clip = self.number)
            # Now that the Transcript Object knows its record number, assign it to the Clip Object
            self.clip_transcript_num = tempTranscript.number
            
        elif self.clip_transcript_num > 0:
            # Load the existing Transcript Record
            tempTranscript = Transcript.Transcript(clip=self.number)
            # Update the Transcript Data
            tempTranscript.text = self.text
            # Save the new Transcript record
            tempTranscript.db_save()
        # Add the Episode keywords back
        for kws in self._kwlist:
            DBInterface.insert_clip_keyword(0, self.number, kws.keywordGroup, kws.keyword, kws.example)
        c.close()

    def db_delete(self, use_transactions=1):
        """Delete this object record from the database."""
        result = 1
        try:
            # Initialize delete operation, begin transaction if necessary
            (db, c) = self._db_start_delete(use_transactions)
            # If this clip serves as a Keyword Example, we should prompt the user about
            # whether it should really be deleted
            kwExampleList = DBInterface.list_all_keyword_examples_for_a_clip(self.number)
            if len(kwExampleList) > 0:
                if len(kwExampleList) == 1:
                    prompt = _('Clip "%s" has been defined as a Keyword Example for Keyword "%s : %s".')
                    data = (self.id, kwExampleList[0][0], kwExampleList[0][1])
                else:
                    prompt = _('Clip "%s" has been defined as a Keyword Example for multiple Keywords.')
                    data = self.id
                if 'unicode' in wx.PlatformInfo:
                    # Encode with UTF-8 rather than TransanaGlobal.encoding because this is a prompt, not DB Data.
                    prompt = unicode(prompt, 'utf8') % data
                else:
                    prompt = prompt % data
                prompt = prompt + _('\nAre you sure you want to delete it?')
                dlg = wx.MessageDialog(None, prompt, _('Delete Clip'), wx.YES_NO | wx.CENTRE | wx.ICON_QUESTION | wx.STAY_ON_TOP)
                if dlg.ShowModal() == wx.ID_NO:
                    dlg.Destroy()
                    # A Transcaction was started and the record was locked in _db_start_delete().  Unlock it here if the
                    # user cancels the delete (after rolling back the Transaction)!
                    if self.isLocked:
                        # c (the database cursor) only exists if the record lock was obtained!
                        # We must roll back the transaction before we unlock the record.
                        c.execute("ROLLBACK")
                        c.close()
                        self.unlock_record()
                    return 0
                else:
                    dlg.Destroy()

            # Detect, Load, and Delete all Clip Notes.
            notes = self.get_note_nums()
            for note_num in notes:
                note = Note.Note(note_num)
                result = result and note.db_delete(0)
                del note
            del notes

            # Okay, theoretically we have a lock on this clip's Transcript, self.trans.  However, that lock
            # prevents us from deleting it!!  Oops.  Therefore, IF we have a legit lock on it, unlock it for
            # the delete.
            if self.isLocked and self.trans.isLocked:
                self.trans.unlock_record()
            # if transcript delete fails, rollback clip delete
            result = result and self.trans.db_delete(0)

            # NOTE:  It is important for the calling routine to delete references to the Keyword Examples
            #        from the screen.  However, that code does not belong in the Clip Object, but in the
            #        user interface.  That is why it is not included here as part of the result.

            # Delete all related references in the ClipKeywords table
            if result:
                DBInterface.delete_all_keywords_for_a_group(0, self.number)

            # Delete the actual record.
            self._db_do_delete(use_transactions, c, result)

            # Cleanup
            c.close()
            self.clear()
        except RecordLockedError, e:
            # if a sub-record is locked, we may need to unlock the Clip record (after rolling back the Transaction)
            if self.isLocked:
                # c (the database cursor) only exists if the record lock was obtained!
                # We must roll back the transaction before we unlock the record.
                c.execute("ROLLBACK")
                c.close()
                self.unlock_record()
            raise e
        except:
            raise
        return result

    def lock_record(self):
        """ Override the DataObject Lock Method """
        # Also lock the Clip Transcript record
        self.trans = Transcript.Transcript(clip=self.number)
        self.trans.lock_record()
        
        # Lock the Clip Record.  Call this second so the Clip is not identified as locked if the
        # Clip Transcript record lock fails.
        DataObject.lock_record(self)
            

    def unlock_record(self):
        """ Override the DataObject Unlock Method """
        # Unlock the Clip Record
        DataObject.unlock_record(self)
        # Also unlock the Clip Transcript record
        self.trans.unlock_record()
        self.trans = None

    def duplicate(self):
        # Inherit duplicate method
        newClip = DataObject.duplicate(self)
        # A new Clip should get a new Clip Transcript!
        newClip.clip_transcript_num = 0
        # Sort Order should not be duplicated!
        newClip.sort_order = 0
        # Copying a Clip should not cause additional Keyword Examples to be created.
        # We need to strip the "example" status for all keywords in the new clip.
        for clipKeyword in newClip.keyword_list:
            clipKeyword.example = 0
        return newClip
        
    def clear_keywords(self):
        """Clear the keyword list."""
        self._kwlist = []
        
    def refresh_keywords(self):
        """Clear the keyword list and refresh it from the database."""
        self._kwlist = []
        kwpairs = DBInterface.list_of_keywords(Clip=self.number)
        for data in kwpairs:
            tempClipKeyword = ClipKeywordObject.ClipKeyword(data[0], data[1], clipNum=self.number, example=data[2])
            self._kwlist.append(tempClipKeyword)
        
    def add_keyword(self, kwg, kw):
        """Add a keyword to the keyword list."""
        # We need to check to see if the keyword is already in the keyword list
        keywordFound = False
        # Iterate through the list
        for clipKeyword in self._kwlist:
            # If we find a match, set the flag and quit looking.
            if (clipKeyword.keywordGroup == kwg) and (clipKeyword.keyword == kw):
                keywordFound = True
                break

        # If the keyword is not found, add it.  (If it's already there, we don't need to do anything!)
        if not keywordFound:
            # Create an appropriate ClipKeyword Object
            tempClipKeyword = ClipKeywordObject.ClipKeyword(kwg, kw, clipNum=self.number)
            # Add it to the Keyword List
            self._kwlist.append(tempClipKeyword)

    def remove_keyword(self, kwg, kw):
        """Remove a keyword from the keyword list.  The value returned by this function can be:
             0  Keyword NOT deleted.  (probably overridden by the user)
             1  Keyword deleted, but it was NOT a Keyword Example
             2  Keyword deleted, and it WAS a Keyword Example. """
        # We need different return codes for failure, success of a Non-Example, and success of an Example.
        # If it's an example, we need to remove the Node on the Database Tree Tab

        # Let's assume the Delete will fail (or be refused by the user) until it actually happens.
        delResult = 0

        # We need to find the keyword in the keyword list
        # Iterate through the keyword list
        for index in range(len(self._kwlist)):

            # Look for the entry to be deleted
            if (self._kwlist[index].keywordGroup == kwg) and (self._kwlist[index].keyword == kw):

                if self._kwlist[index].example == 1:
                    if 'unicode' in wx.PlatformInfo:
                        # Encode with UTF-8 rather than TransanaGlobal.encoding because this is a prompt, not DB Data.
                        prompt = unicode(_('Clip "%s" has been designated as an example of Keyword "%s : %s".\nRemoving this Keyword from the Clip will also remove the Clip as a Keyword Example.\n\nDo you want to remove Clip "%s" as an example of Keyword "%s : %s"?'), 'utf8')
                    else:
                        prompt = _('Clip "%s" has been designated as an example of Keyword "%s : %s".\nRemoving this Keyword from the Clip will also remove the Clip as a Keyword Example.\n\nDo you want to remove Clip "%s" as an example of Keyword "%s : %s"?')
                    dlg = wx.MessageDialog(TransanaGlobal.menuWindow, prompt % (self.id, kwg, kw, self.id, kwg, kw), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result == wx.ID_YES:
                        # If the entry is found and the user confirms, delete it
                        del self._kwlist[index]
                        delResult = 2
                else:
                    # If the entry is found, delete it and stop looking
                    del self._kwlist[index]
                    delResult = 1
                # Once the entry has been found, stop looking for it
                break
            
        # Signal whether the delete was successful
        return delResult

    def has_keyword(self, kwg, kw):
        """ Determines if the Episode has a given keyword assigned """
        # Assume the result will be false
        res = False
        # Iterate through the keyword list
        for keyword in self.keyword_list:
            # See if the text passed in matches the strings in the keyword objects in the keyword list
            if (kwg == keyword.keywordGroup) and (kw == keyword.keyword):
                # If so, signal that it HAS been found
                res = True
                # If found, we don't need to look any more!
                break
        # Return the results
        return res

    
# Private methods    

    def _load_row(self, r):
        self.number = r['ClipNum']
        self.id = r['ClipID']
        self.comment = r['ClipComment']
        self.collection_num = r['CollectNum']
        self.collection_id = r['CollectID']
        self.episode_num = r['EpisodeNum']
        # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
        self.transcript_num = r['TranscriptNum']
        self.clip_transcript_num = r['ClipTranscriptNum']
        self.media_filename = r['MediaFile']
        self.clip_start = r['ClipStart']
        self.clip_stop = r['ClipStop']
        self.sort_order = r['SortOrder']

        # Okay, this isn't so straight-forward any more.
        # With MySQL for Python 0.9.x, r['RTFText'] is of type str.
        # With MySQL for Python 1.2.0, r['RTFText'] is of type array.  It could then either be a
        # character string (typecode == 'c') or a unicode string (typecode == 'u'), which then
        # need to be interpreted differently.

        if type(r['RTFText']).__name__ == 'array':
            if r['RTFText'].typecode == 'u':
                self.text = r['RTFText'].tounicode()
            else:
                self.text = r['RTFText'].tostring()
        else:
            self.text = r['RTFText']

        # We need to make sure the text is in the appropriate encoding
        if 'unicode' in wx.PlatformInfo:
            if type(self.text).__name__ == 'str':
                self.text = unicode(self.text, TransanaGlobal.encoding)
        # If we're in Unicode mode, we need to encode the data from the database appropriately.
        # (unicode(var, TransanaGlobal.encoding) doesn't work, as the strings are already unicode, yet aren't decoded.)
        if 'unicode' in wx.PlatformInfo:
            self.id = DBInterface.ProcessDBDataForUTF8Encoding(self.id)
            self.comment = DBInterface.ProcessDBDataForUTF8Encoding(self.comment)
            self.collection_id = DBInterface.ProcessDBDataForUTF8Encoding(self.collection_id)
            self.media_filename = DBInterface.ProcessDBDataForUTF8Encoding(self.media_filename)

        # Remember whether the MediaFile uses the VideoRoot Folder or not.
        # Detection of the use of the Video Root Path is platform-dependent.
        if wx.Platform == "__WXMSW__":
            # On Windows, check for a colon in the position, which signals the presence or absence of a drive letter
            self.useVideoRoot = (self.media_filename[1] != ':')
        else:
            # On Mac OS-X and *nix, check for a slash in the first position for the root folder designation
            self.useVideoRoot = (self.media_filename[0] != '/')
        # If we are using the Video Root Path, add it to the Filename
        if self.useVideoRoot:
            self.media_filename = TransanaGlobal.configData.videoPath + self.media_filename


    def _sync_collection(self):
        """Synchronize the Collection ID property to reflect the current state
        of the Collection Number property."""
        # For some reason the Delphi Transana didn't have anything like this
        # going on, which is especially puzzling since I can't figure out how
        # the save worked.
        # Comment by DKW -- Talk to me.  I can explain how it worked pretty easily.
        tempCollection = Collection.Collection(self.collection_num)
        self.collection_id = tempCollection.id
        
    def _get_col_num(self):
        return self._col_num
    def _set_col_num(self, num):
        self._col_num = num
    def _del_col_num(self):
        self._col_num = 0

    def _get_ep_num(self):
        return self._ep_num
    def _set_ep_num(self, num):
        self._ep_num = num
    def _del_ep_num(self):
        self._ep_num = 0

    def _get_t_num(self):
        return self._t_num
    def _set_t_num(self, num):
        self._t_num = num
    def _del_t_num(self):
        self._t_num = 0

    def _get_clip_transcript_num(self):
        return self._clip_transcript_num
    def _set_clip_transcript_num(self, num):
        self._clip_transcript_num = num
    def _del_clip_transcript_num(self):
        self._clip_transcript_num = 0

    def _get_fname(self):
        return self._fname.replace('\\', '/')
    def _set_fname(self, fname):
        self._fname = fname
    def _del_fname(self):
        self._fname = ""

    def _get_clip_start(self):
        return self._clip_start
    def _set_clip_start(self, cs):
        self._clip_start = cs
    def _del_clip_start(self):
        self._clip_start = -1

    def _get_clip_stop(self):
        return self._clip_stop
    def _set_clip_stop(self, cs):
        self._clip_stop = cs
    def _del_clip_stop(self):
        self._clip_stop = -1

    def _get_sort_order(self):
        return self._sort_order
    def _set_sort_order(self, so):
        self._sort_order = so
    def _del_sort_order(self):
        self._sort_order = 0

    def _get_kwlist(self):
        return self._kwlist
    def _set_kwlist(self, kwlist):
        self._kwlist = kwlist
    def _del_kwlist(self):
        self._kwlist = []

    # Clips only know originating Episode Number, which can be used to find the Series ID and Episode ID.
    # For the sake of efficiency, whichever is called first loads both values.
    def _get_series_id(self):
        if self._series_id == "":
            try:
                tempEpisode = Episode.Episode(self.episode_num)
                self._series_id = tempEpisode.series_id
                self._episode_id = tempEpisode.id
            except:
                pass
            return self._series_id
        else:
            return self._series_id
        
    # Clips only know originating Episode Number, which can be used to find the Series ID and Episode ID.
    # For the sake of efficiency, whichever is called first loads both values.
    def _get_episode_id(self):
        if self._episode_id == "":
            try:
                tempEpisode = Episode.Episode(self.episode_num)
                self._series_id = tempEpisode.series_id
                self._episode_id = tempEpisode.id
            except:
                pass
            return self._episode_id
        else:
            return self._episode_id

# Public properties
    collection_num = property(_get_col_num, _set_col_num, _del_col_num,
                        """Collection number to which the clip belongs.""")
    episode_num = property(_get_ep_num, _set_ep_num, _del_ep_num,
                        """Number of episode from which this Clip was taken.""")
    # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
    transcript_num = property(_get_t_num, _set_t_num, _del_t_num,
                        """Number of the transcript from which this Clip was taken.""")
    clip_transcript_num = property(_get_clip_transcript_num, _set_clip_transcript_num, _del_clip_transcript_num,
                        """Number of the Clip's transcript record in the Transcript Table.""")
    media_filename = property(_get_fname, _set_fname, _del_fname,
                        """The name (including path) of the media file.""")
    clip_start = property(_get_clip_start, _set_clip_start, _del_clip_start,
                        """Starting position of the Clip in the media file.""")
    clip_stop = property(_get_clip_stop, _set_clip_stop, _del_clip_stop,
                        """Ending position of the Clip in the media file.""")
    sort_order = property(_get_sort_order, _set_sort_order, _del_sort_order,
                        """Sort Order position within the parent Collection.""")
    keyword_list = property(_get_kwlist, _set_kwlist, _del_kwlist,
                        """The list of keywords that have been applied to
                        the Clip.""")
    series_id = property(_get_series_id, None, None,
                        "ID for the Series from which this Clip was created, if the (bridge) Episode still exists")
    episode_id = property(_get_episode_id, None, None,
                        "ID for the Episode from which this Clip was created, if it still exists")
