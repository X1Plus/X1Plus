# imported from https://github.com/cubinator/ext4
# GPLv3, cubinator

import ctypes
import functools
import io
import math
import queue



########################################################################################################################
#####################################################   HELPERS   ######################################################
########################################################################################################################

def wcscmp (str_a, str_b):
    """
    Standard library wcscmp
    """
    for a, b in zip(str_a, str_b):
        tmp = ord(a) - ord(b)
        if tmp != 0: return -1 if tmp < 0 else 1

    tmp = len(str_a) - len(str_b)
    return -1 if tmp < 0 else 1 if tmp > 0 else 0



########################################################################################################################
####################################################   EXCEPTIONS   ####################################################
########################################################################################################################

class Ext4Error (Exception):
    """
    Base class for all custom errors
    """
    pass

class BlockMapError (Ext4Error):
    """
    Raised, when a requested file_block is not mapped to disk
    """
    pass

class EndOfStreamError (Ext4Error):
    """
    Raised, when BlockReader reads beyond the end of the volume's underlying stream
    """
    pass

class MagicError (Ext4Error):
    """
    Raised, when a structures magic value is wrong and ignore_magic is False
    """
    pass



########################################################################################################################
####################################################   LOW LEVEL   #####################################################
########################################################################################################################

class ext4_struct (ctypes.LittleEndianStructure):
    """
    Simplifies access to *_lo and *_hi fields
    """
    def __getattr__ (self, name):
        """
        Enables reading *_lo and *_hi fields together.
        """
        try:
            # Combining *_lo and *_hi fields
            lo_field = ctypes.LittleEndianStructure.__getattribute__(type(self), name + "_lo")
            size = lo_field.size

            lo = lo_field.__get__(self)
            hi = ctypes.LittleEndianStructure.__getattribute__(self, name + "_hi")

            return (hi << (8 * size)) | lo
        except AttributeError:
            return ctypes.LittleEndianStructure.__getattribute__(self, name)

    def __setattr__ (self, name, value):
        """
        Enables setting *_lo and *_hi fields together.
        """
        try:
            # Combining *_lo and *_hi fields
            lo_field = lo_field = ctypes.LittleEndianStructure.__getattribute__(type(self), name + "_lo")
            size = lo_field.size

            lo_field.__set__(self, value & ((1 << (8 * size)) - 1))
            ctypes.LittleEndianStructure.__setattr__(self, name + "_hi", value >> (8 * size))
        except AttributeError:
            ctypes.LittleEndianStructure.__setattr__(self, name, value)



class ext4_dir_entry_2 (ext4_struct):
    _fields_ = [
        ("inode", ctypes.c_uint),       # 0x0
        ("rec_len", ctypes.c_ushort),   # 0x4
        ("name_len", ctypes.c_ubyte),   # 0x6
        ("file_type", ctypes.c_ubyte)   # 0x7
        # Variable length field "name" missing at 0x8
    ]

    def _from_buffer_copy (raw, offset = 0, platform64 = True):
        struct = ext4_dir_entry_2.from_buffer_copy(raw, offset)
        struct.name = raw[offset + 0x8 : offset + 0x8 + struct.name_len]
        return struct



class ext4_extent (ext4_struct):
    _fields_ = [
        ("ee_block", ctypes.c_uint),      # 0x0000
        ("ee_len", ctypes.c_ushort),      # 0x0004
        ("ee_start_hi", ctypes.c_ushort), # 0x0006
        ("ee_start_lo", ctypes.c_uint)    # 0x0008
    ]



class ext4_extent_header (ext4_struct):
    _fields_ = [
        ("eh_magic", ctypes.c_ushort),   # 0x0000, Must be 0xF30A
        ("eh_entries", ctypes.c_ushort), # 0x0002
        ("eh_max", ctypes.c_ushort),     # 0x0004
        ("eh_depth", ctypes.c_ushort),   # 0x0006
        ("eh_generation", ctypes.c_uint) # 0x0008
    ]



class ext4_extent_idx (ext4_struct):
    _fields_ = [
        ("ei_block", ctypes.c_uint),     # 0x0000
        ("ei_leaf_lo", ctypes.c_uint),   # 0x0004
        ("ei_leaf_hi", ctypes.c_ushort), # 0x0008
        ("ei_unused", ctypes.c_ushort)   # 0x000A
    ]



class ext4_group_descriptor (ext4_struct):
    _fields_ = [
        ("bg_block_bitmap_lo", ctypes.c_uint),        # 0x0000
        ("bg_inode_bitmap_lo", ctypes.c_uint),        # 0x0004
        ("bg_inode_table_lo", ctypes.c_uint),         # 0x0008
        ("bg_free_blocks_count_lo", ctypes.c_ushort), # 0x000C
        ("bg_free_inodes_count_lo", ctypes.c_ushort), # 0x000E
        ("bg_used_dirs_count_lo", ctypes.c_ushort),   # 0x0010
        ("bg_flags", ctypes.c_ushort),                # 0x0012
        ("bg_exclude_bitmap_lo", ctypes.c_uint),      # 0x0014
        ("bg_block_bitmap_csum_lo", ctypes.c_ushort), # 0x0018
        ("bg_inode_bitmap_csum_lo", ctypes.c_ushort), # 0x001A
        ("bg_itable_unused_lo", ctypes.c_ushort),     # 0x001C
        ("bg_checksum", ctypes.c_ushort),             # 0x001E

        # 64-bit fields
        ("bg_block_bitmap_hi", ctypes.c_uint),        # 0x0020
        ("bg_inode_bitmap_hi", ctypes.c_uint),        # 0x0024
        ("bg_inode_table_hi", ctypes.c_uint),         # 0x0028
        ("bg_free_blocks_count_hi", ctypes.c_ushort), # 0x002C
        ("bg_free_inodes_count_hi", ctypes.c_ushort), # 0x002E
        ("bg_used_dirs_count_hi", ctypes.c_ushort),   # 0x0030
        ("bg_itable_unused_hi", ctypes.c_ushort),     # 0x0032
        ("bg_exclude_bitmap_hi", ctypes.c_uint),      # 0x0034
        ("bg_block_bitmap_csum_hi", ctypes.c_ushort), # 0x0038
        ("bg_inode_bitmap_csum_hi", ctypes.c_ushort), # 0x003A
        ("bg_reserved", ctypes.c_uint),               # 0x003C
    ]

    def _from_buffer_copy (raw, offset = 0, platform64 = True):
        struct = ext4_group_descriptor.from_buffer_copy(raw, offset)

        if not platform64:
            struct.bg_block_bitmap_hi = 0
            struct.bg_inode_bitmap_hi = 0
            struct.bg_inode_table_hi = 0
            struct.bg_free_blocks_count_hi = 0
            struct.bg_free_inodes_count_hi = 0
            struct.bg_used_dirs_count_hi = 0
            struct.bg_itable_unused_hi = 0
            struct.bg_exclude_bitmap_hi = 0
            struct.bg_block_bitmap_csum_hi = 0
            struct.bg_inode_bitmap_csum_hi = 0
            struct.bg_reserved = 0

        return struct



class ext4_inode (ext4_struct):
    EXT2_GOOD_OLD_INODE_SIZE = 128 # Every field passing 128 bytes is "additional data", whose size is specified by i_extra_isize.

    # i_mode
    S_IXOTH  =    0x1 # Others can execute
    S_IWOTH  =    0x2 # Others can write
    S_IROTH  =    0x4 # Others can read
    S_IXGRP  =    0x8 # Group can execute
    S_IWGRP  =   0x10 # Group can write
    S_IRGRP  =   0x20 # Group can read
    S_IXUSR  =   0x40 # Owner can execute
    S_IWUSR  =   0x80 # Owner can write
    S_IRUSR  =  0x100 # Owner can read
    S_ISVTX  =  0x200 # Sticky bit (only owner can delete)
    S_ISGID  =  0x400 # Set GID (execute with privileges of group owner of the file's group)
    S_ISUID  =  0x800 # Set UID (execute with privileges of the file's owner)
    S_IFIFO  = 0x1000 # FIFO device (named pipe)
    S_IFCHR  = 0x2000 # Character device (raw, unbuffered, aligned, direct access to hardware storage)
    S_IFDIR  = 0x4000 # Directory
    S_IFBLK  = 0x6000 # Block device (buffered, arbitrary access to storage)
    S_IFREG  = 0x8000 # Regular file
    S_IFLNK  = 0xA000 # Symbolic link
    S_IFSOCK = 0xC000 # Socket

    # i_flags
    EXT4_INDEX_FL       =     0x1000 # Uses hash trees
    EXT4_EXTENTS_FL     =    0x80000 # Uses extents
    EXT4_EA_INODE_FL    =   0x200000 # Inode stores large xattr
    EXT4_INLINE_DATA_FL = 0x10000000 # Has inline data

    _fields_ = [
        ("i_mode", ctypes.c_ushort),             # 0x0000
        ("i_uid_lo", ctypes.c_ushort),           # 0x0002, Originally named i_uid
        ("i_size_lo", ctypes.c_uint),            # 0x0004
        ("i_atime", ctypes.c_uint),              # 0x0008
        ("i_ctime", ctypes.c_uint),              # 0x000C
        ("i_mtime", ctypes.c_uint),              # 0x0010
        ("i_dtime", ctypes.c_uint),              # 0x0014
        ("i_gid_lo", ctypes.c_ushort),           # 0x0018, Originally named i_gid
        ("i_links_count", ctypes.c_ushort),      # 0x001A
        ("i_blocks_lo", ctypes.c_uint),          # 0x001C
        ("i_flags", ctypes.c_uint),              # 0x0020
        ("osd1", ctypes.c_uint),                 # 0x0024
        ("i_block", ctypes.c_uint * 15),         # 0x0028
        ("i_generation", ctypes.c_uint),         # 0x0064
        ("i_file_acl_lo", ctypes.c_uint),        # 0x0068
        ("i_size_hi", ctypes.c_uint),            # 0x006C, Originally named i_size_high
        ("i_obso_faddr", ctypes.c_uint),         # 0x0070
        ("i_osd2_blocks_high", ctypes.c_ushort), # 0x0074, Originally named i_osd2.linux2.l_i_blocks_high
        ("i_file_acl_hi", ctypes.c_ushort),      # 0x0076, Originally named i_osd2.linux2.l_i_file_acl_high
        ("i_uid_hi", ctypes.c_ushort),           # 0x0078, Originally named i_osd2.linux2.l_i_uid_high
        ("i_gid_hi", ctypes.c_ushort),           # 0x007A, Originally named i_osd2.linux2.l_i_gid_high
        ("i_osd2_checksum_lo", ctypes.c_ushort), # 0x007C, Originally named i_osd2.linux2.l_i_checksum_lo
        ("i_osd2_reserved", ctypes.c_ushort),    # 0x007E, Originally named i_osd2.linux2.l_i_reserved
        ("i_extra_isize", ctypes.c_ushort),      # 0x0080
        ("i_checksum_hi", ctypes.c_ushort),      # 0x0082
        ("i_ctime_extra", ctypes.c_uint),        # 0x0084
        ("i_mtime_extra", ctypes.c_uint),        # 0x0088
        ("i_atime_extra", ctypes.c_uint),        # 0x008C
        ("i_crtime", ctypes.c_uint),             # 0x0090
        ("i_crtime_extra", ctypes.c_uint),       # 0x0094
        ("i_version_hi", ctypes.c_uint),         # 0x0098
        ("i_projid", ctypes.c_uint),             # 0x009C
    ]



class ext4_superblock (ext4_struct):
    EXT2_MIN_DESC_SIZE = 0x20 # Default value for s_desc_size, if INCOMPAT_64BIT is not set (NEEDS CONFIRMATION)
    EXT2_MIN_DESC_SIZE_64BIT = 0x40 # Default value for s_desc_size, if INCOMPAT_64BIT is set

    # s_feature_incompat
    INCOMPAT_64BIT    = 0x80 # Uses 64-bit features (e.g. *_hi structure fields in ext4_group_descriptor)
    INCOMPAT_FILETYPE =  0x2 # Directory entries record file type (instead of inode flags)

    _fields_ = [
        ("s_inodes_count", ctypes.c_uint),                 # 0x0000
        ("s_blocks_count_lo", ctypes.c_uint),              # 0x0004
        ("s_r_blocks_count_lo", ctypes.c_uint),            # 0x0008
        ("s_free_blocks_count_lo", ctypes.c_uint),         # 0x000C
        ("s_free_inodes_count", ctypes.c_uint),            # 0x0010
        ("s_first_data_block", ctypes.c_uint),             # 0x0014
        ("s_log_block_size", ctypes.c_uint),               # 0x0018
        ("s_log_cluster_size", ctypes.c_uint),             # 0x001C
        ("s_blocks_per_group", ctypes.c_uint),             # 0x0020
        ("s_clusters_per_group", ctypes.c_uint),           # 0x0024
        ("s_inodes_per_group", ctypes.c_uint),             # 0x0028
        ("s_mtime", ctypes.c_uint),                        # 0x002C
        ("s_wtime", ctypes.c_uint),                        # 0x0030
        ("s_mnt_count", ctypes.c_ushort),                  # 0x0034
        ("s_max_mnt_count", ctypes.c_ushort),              # 0x0036
        ("s_magic", ctypes.c_ushort),                      # 0x0038, Must be 0xEF53
        ("s_state", ctypes.c_ushort),                      # 0x003A
        ("s_errors", ctypes.c_ushort),                     # 0x003C
        ("s_minor_rev_level", ctypes.c_ushort),            # 0x003E
        ("s_lastcheck", ctypes.c_uint),                    # 0x0040
        ("s_checkinterval", ctypes.c_uint),                # 0x0044
        ("s_creator_os", ctypes.c_uint),                   # 0x0048
        ("s_rev_level", ctypes.c_uint),                    # 0x004C
        ("s_def_resuid", ctypes.c_ushort),                 # 0x0050
        ("s_def_resgid", ctypes.c_ushort),                 # 0x0052
        ("s_first_ino", ctypes.c_uint),                    # 0x0054
        ("s_inode_size", ctypes.c_ushort),                 # 0x0058
        ("s_block_group_nr", ctypes.c_ushort),             # 0x005A
        ("s_feature_compat", ctypes.c_uint),               # 0x005C
        ("s_feature_incompat", ctypes.c_uint),             # 0x0060
        ("s_feature_ro_compat", ctypes.c_uint),            # 0x0064
        ("s_uuid", ctypes.c_ubyte * 16),                   # 0x0068
        ("s_volume_name", ctypes.c_char * 16),             # 0x0078
        ("s_last_mounted", ctypes.c_char * 64),            # 0x0088
        ("s_algorithm_usage_bitmap", ctypes.c_uint),       # 0x00C8
        ("s_prealloc_blocks", ctypes.c_ubyte),             # 0x00CC
        ("s_prealloc_dir_blocks", ctypes.c_ubyte),         # 0x00CD
        ("s_reserved_gdt_blocks", ctypes.c_ushort),        # 0x00CE
        ("s_journal_uuid", ctypes.c_ubyte * 16),           # 0x00D0
        ("s_journal_inum", ctypes.c_uint),                 # 0x00E0
        ("s_journal_dev", ctypes.c_uint),                  # 0x00E4
        ("s_last_orphan", ctypes.c_uint),                  # 0x00E8
        ("s_hash_seed", ctypes.c_uint * 4),                # 0x00EC
        ("s_def_hash_version", ctypes.c_ubyte),            # 0x00FC
        ("s_jnl_backup_type", ctypes.c_ubyte),             # 0x00FD
        ("s_desc_size", ctypes.c_ushort),                  # 0x00FE
        ("s_default_mount_opts", ctypes.c_uint),           # 0x0100
        ("s_first_meta_bg", ctypes.c_uint),                # 0x0104
        ("s_mkfs_time", ctypes.c_uint),                    # 0x0108
        ("s_jnl_blocks", ctypes.c_uint * 17),              # 0x010C

        # 64-bit fields
        ("s_blocks_count_hi", ctypes.c_uint),              # 0x0150
        ("s_r_blocks_count_hi", ctypes.c_uint),            # 0x0154
        ("s_free_blocks_count_hi", ctypes.c_uint),         # 0x0158
        ("s_min_extra_isize", ctypes.c_ushort),            # 0x015C
        ("s_want_extra_isize", ctypes.c_ushort),           # 0x015E
        ("s_flags", ctypes.c_uint),                        # 0x0160
        ("s_raid_stride", ctypes.c_ushort),                # 0x0164
        ("s_mmp_interval", ctypes.c_ushort),               # 0x0166
        ("s_mmp_block", ctypes.c_ulonglong),               # 0x0168
        ("s_raid_stripe_width", ctypes.c_uint),            # 0x0170
        ("s_log_groups_per_flex", ctypes.c_ubyte),         # 0x0174
        ("s_checksum_type", ctypes.c_ubyte),               # 0x0175
        ("s_reserved_pad", ctypes.c_ushort),               # 0x0176
        ("s_kbytes_written", ctypes.c_ulonglong),          # 0x0178
        ("s_snapshot_inum", ctypes.c_uint),                # 0x0180
        ("s_snapshot_id", ctypes.c_uint),                  # 0x0184
        ("s_snapshot_r_blocks_count", ctypes.c_ulonglong), # 0x0188
        ("s_snapshot_list", ctypes.c_uint),                # 0x0190
        ("s_error_count", ctypes.c_uint),                  # 0x0194
        ("s_first_error_time", ctypes.c_uint),             # 0x0198
        ("s_first_error_ino", ctypes.c_uint),              # 0x019C
        ("s_first_error_block", ctypes.c_ulonglong),       # 0x01A0
        ("s_first_error_func", ctypes.c_ubyte * 32),       # 0x01A8
        ("s_first_error_line", ctypes.c_uint),             # 0x01C8
        ("s_last_error_time", ctypes.c_uint),              # 0x01CC
        ("s_last_error_ino", ctypes.c_uint),               # 0x01D0
        ("s_last_error_line", ctypes.c_uint),              # 0x01D4
        ("s_last_error_block", ctypes.c_ulonglong),        # 0x01D8
        ("s_last_error_func", ctypes.c_ubyte * 32),        # 0x01E0
        ("s_mount_opts", ctypes.c_ubyte * 64),             # 0x0200
        ("s_usr_quota_inum", ctypes.c_uint),               # 0x0240
        ("s_grp_quota_inum", ctypes.c_uint),               # 0x0244
        ("s_overhead_blocks", ctypes.c_uint),              # 0x0248
        ("s_backup_bgs", ctypes.c_uint * 2),               # 0x024C
        ("s_encrypt_algos", ctypes.c_ubyte * 4),           # 0x0254
        ("s_encrypt_pw_salt", ctypes.c_ubyte * 16),        # 0x0258
        ("s_lpf_ino", ctypes.c_uint),                      # 0x0268
        ("s_prj_quota_inum", ctypes.c_uint),               # 0x026C
        ("s_checksum_seed", ctypes.c_uint),                # 0x0270
        ("s_reserved", ctypes.c_uint * 98),                # 0x0274
        ("s_checksum", ctypes.c_uint)                      # 0x03FC
    ]

    def _from_buffer_copy (raw, platform64 = True):
        struct = ext4_superblock.from_buffer_copy(raw)

        if not platform64:
            struct.s_blocks_count_hi = 0
            struct.s_r_blocks_count_hi = 0
            struct.s_free_blocks_count_hi = 0
            struct.s_min_extra_isize = 0
            struct.s_want_extra_isize = 0
            struct.s_flags = 0
            struct.s_raid_stride = 0
            struct.s_mmp_interval = 0
            struct.s_mmp_block = 0
            struct.s_raid_stripe_width = 0
            struct.s_log_groups_per_flex = 0
            struct.s_checksum_type = 0
            struct.s_reserved_pad = 0
            struct.s_kbytes_written = 0
            struct.s_snapshot_inum = 0
            struct.s_snapshot_id = 0
            struct.s_snapshot_r_blocks_count = 0
            struct.s_snapshot_list = 0
            struct.s_error_count = 0
            struct.s_first_error_time = 0
            struct.s_first_error_ino = 0
            struct.s_first_error_block = 0
            struct.s_first_error_func = 0
            struct.s_first_error_line = 0
            struct.s_last_error_time = 0
            struct.s_last_error_ino = 0
            struct.s_last_error_line = 0
            struct.s_last_error_block = 0
            struct.s_last_error_func = 0
            struct.s_mount_opts = 0
            struct.s_usr_quota_inum = 0
            struct.s_grp_quota_inum = 0
            struct.s_overhead_blocks = 0
            struct.s_backup_bgs = 0
            struct.s_encrypt_algos = 0
            struct.s_encrypt_pw_salt = 0
            struct.s_lpf_ino = 0
            struct.s_prj_quota_inum = 0
            struct.s_checksum_seed = 0
            struct.s_reserved = 0
            struct.s_checksum = 0

        if struct.s_desc_size == 0:
            if (struct.s_feature_incompat & ext4_superblock.INCOMPAT_64BIT) == 0:
                struct.s_desc_size = ext4_superblock.EXT2_MIN_DESC_SIZE
            else:
                struct.s_desc_size = ext4_superblock.EXT2_MIN_DESC_SIZE_64BIT

        return struct



class ext4_xattr_entry (ext4_struct):
    _fields_ = [
        ("e_name_len", ctypes.c_ubyte),      # 0x00
        ("e_name_index", ctypes.c_ubyte),    # 0x01
        ("e_value_offs", ctypes.c_ushort),   # 0x02
        ("e_value_inum", ctypes.c_uint),     # 0x04
        ("e_value_size", ctypes.c_uint),     # 0x08
        ("e_hash", ctypes.c_uint)            # 0x0C
        # Variable length field "e_name" missing at 0x10
    ]

    def _from_buffer_copy (raw, offset = 0, platform64 = True):
        struct = ext4_xattr_entry.from_buffer_copy(raw, offset)
        struct.e_name = raw[offset + 0x10 : offset + 0x10 + struct.e_name_len]
        return struct

    @property
    def _size (self): return 4 * ((ctypes.sizeof(type(self)) + self.e_name_len + 3) // 4) # 4-byte alignment



class ext4_xattr_header (ext4_struct):
    _fields_ = [
        ("h_magic", ctypes.c_uint),        # 0x0, Must be 0xEA020000
        ("h_refcount", ctypes.c_uint),     # 0x4
        ("h_blocks", ctypes.c_uint),       # 0x8
        ("h_hash", ctypes.c_uint),         # 0xC
        ("h_checksum", ctypes.c_uint),     # 0x10
        ("h_reserved", ctypes.c_uint * 3), # 0x14
    ]



class ext4_xattr_ibody_header (ext4_struct):
    _fields_ = [
        ("h_magic", ctypes.c_uint) # 0x0, Must be 0xEA020000
    ]



class InodeType:
    UNKNOWN          =  0x0 # Unknown file type
    FILE             =  0x1 # Regular file
    DIRECTORY        =  0x2 # Directory
    CHARACTER_DEVICE =  0x3 # Character device
    BLOCK_DEVICE     =  0x4 # Block device
    FIFO             =  0x5 # FIFO
    SOCKET           =  0x6 # Socket
    SYMBOLIC_LINK    =  0x7 # Symbolic link
    CHECKSUM         = 0xDE # Checksum entry; not really a file type, but a type of directory entry



########################################################################################################################
####################################################   HIGH LEVEL   ####################################################
########################################################################################################################

class MappingEntry:
    """
    Helper class: This class maps block_count file blocks indexed by file_block_idx to the associated disk blocks indexed
    by disk_block_idx.
    """
    def __init__ (self, file_block_idx, disk_block_idx, block_count = 1):
        """
        Initialize a MappingEntry instance with given file_block_idx, disk_block_idx and block_count.
        """
        self.file_block_idx = file_block_idx
        self.disk_block_idx = disk_block_idx
        self.block_count = block_count

    def __iter__ (self):
        """
        Can be used to convert an MappingEntry into a tuple (file_block_idx, disk_block_idx, block_count).
        """
        yield self.file_block_idx
        yield self.disk_block_idx
        yield self.block_count

    def __repr__ (self):
        return f"{type(self).__name__:s}({self.file_block_idx!r:s}, {self.disk_block_idx!r:s}, {self.block_count!r:s})"

    def copy (self):
        return MappingEntry(self.file_block_idx, self.disk_block_idx, self.block_count)

    def create_mapping (*entries):
        """
        Converts a list of 2-tuples (disk_block_idx, block_count) into a list of MappingEntry instances
        """
        file_block_idx = 0
        result = [None] * len(entries)

        for i, entry in enumerate(entries):
            disk_block_idx, block_count = entry
            result[i] = MappingEntry(file_block_idx, disk_block_idx, block_count)
            file_block_idx += block_count

        return result

    def optimize (entries):
        """
        Sorts and stiches together a list of MappingEntry instances
        """
        entries.sort(key = lambda entry: entry.file_block_idx)

        idx = 0
        while idx < len(entries):
            while idx + 1 < len(entries) \
                    and entries[idx].file_block_idx + entries[idx].block_count == entries[idx + 1].file_block_idx \
                    and entries[idx].disk_block_idx + entries[idx].block_count == entries[idx + 1].disk_block_idx:
                tmp = entries.pop(idx + 1)
                entries[idx].block_count += tmp.block_count

            idx += 1

# None of the following classes preserve the underlying stream's current seek.

class Volume:
    """
    Provides functionality for reading ext4 volumes
    """

    ROOT_INODE = 2

    def __init__ (self, stream, offset = 0, ignore_flags = False, ignore_magic = False):
        """
        Initializes a new ext4 reader at a given offset in stream. If ignore_magic is True, no exception will be thrown,
        when a structure with wrong magic number is found. Analogously passing True to ignore_flags suppresses Exception
        caused by wrong flags.
        """
        self.ignore_flags = ignore_flags
        self.ignore_magic = ignore_magic
        self.offset = offset
        self.platform64 = True # Initial value needed for Volume.read_struct
        self.stream = stream

        # Superblock
        self.superblock = self.read_struct(ext4_superblock, 0x400)
        self.platform64 = (self.superblock.s_feature_incompat & ext4_superblock.INCOMPAT_64BIT) != 0

        if not ignore_magic and self.superblock.s_magic != 0xEF53:
            raise MagicError(f"Invalid magic value in superblock: 0x{self.superblock.s_magic:04X} (expected 0xEF53)")

        # Group descriptors
        self.group_descriptors = [None] * (self.superblock.s_inodes_count // self.superblock.s_inodes_per_group)

        group_desc_table_offset = (0x400 // self.block_size + 1) * self.block_size # First block after superblock
        for group_desc_idx in range(len(self.group_descriptors)):
            group_desc_offset = group_desc_table_offset + group_desc_idx * self.superblock.s_desc_size
            self.group_descriptors[group_desc_idx] = self.read_struct(ext4_group_descriptor, group_desc_offset)

    def __repr__ (self):
        return f"{type(self).__name__:s}(volume_name = {self.superblock.s_volume_name!r:s}, uuid = {self.uuid!r:s}, last_mounted = {self.superblock.s_last_mounted!r:s})"

    @property
    def block_size (self):
        """
        Returns the volume's block size in bytes.
        """
        return 1 << (10 + self.superblock.s_log_block_size)

    def get_inode (self, inode_idx):
        """
        Returns an Inode instance representing the inode specified by its index inode_idx.
        """
        group_idx, inode_table_entry_idx = self.get_inode_group(inode_idx)

        inode_table_offset = self.group_descriptors[group_idx].bg_inode_table * self.block_size
        inode_offset = inode_table_offset + inode_table_entry_idx * self.superblock.s_inode_size

        return Inode(self, inode_offset, inode_idx)

    def get_inode_group (self, inode_idx):
        """
        Returns a tuple (group_idx, inode_table_entry_idx)
        """
        group_idx = (inode_idx - 1) // self.superblock.s_inodes_per_group
        inode_table_entry_idx = (inode_idx - 1) % self.superblock.s_inodes_per_group
        return (group_idx, inode_table_entry_idx)

    def read (self, offset, byte_len):
        """
        Returns byte_len bytes at offset within this volume.
        """
        if self.offset + offset != self.stream.tell():
            self.stream.seek(self.offset + offset, io.SEEK_SET)

        return self.stream.read(byte_len)

    def read_struct (self, structure, offset, platform64 = None):
        """
        Interprets the bytes at offset as structure and returns the interpreted instance
        """
        raw = self.read(offset, ctypes.sizeof(structure))

        if hasattr(structure, "_from_buffer_copy"):
            return structure._from_buffer_copy(raw, platform64 = platform64 if platform64 != None else self.platform64)
        else:
            return structure.from_buffer_copy(raw)

    @property
    def root (self):
        """
        Returns the volume's root inode
        """
        return self.get_inode(Volume.ROOT_INODE)

    @property
    def uuid (self):
        """
        Returns the volume's UUID in the format XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.
        """
        uuid = self.superblock.s_uuid
        uuid = [uuid[:4], uuid[4 : 6], uuid[6 : 8], uuid[8 : 10], uuid[10:]]
        return "-".join("".join(f"{c:02X}" for c in part) for part in uuid)



class Inode:
    """
    Provides functionality for parsing inodes and accessing their raw data
    """

    def __init__ (self, volume, offset, inode_idx):
        """
        Initializes a new inode parser at the specified offset within the specified volume. file_type is the file type
        of the inode as given by the directory entry referring to this inode.
        """
        self.inode_idx = inode_idx
        self.offset = offset
        self.volume = volume

        self.inode = volume.read_struct(ext4_inode, offset)

    def __len__ (self):
        """
        Returns the length in bytes of the content referenced by this inode.
        """
        return self.inode.i_size

    def __repr__ (self):
        if self.inode_idx != None:
            return f"{type(self).__name__:s}(inode_idx = {self.inode_idx!r:s}, offset = 0x{self.offset:X}, volume_uuid = {self.volume.uuid!r:s})"
        else:
            return f"{type(self).__name__:s}(offset = 0x{self.offset:X}, volume_uuid = {self.volume.uuid!r:s})"

    def _parse_xattrs (self, raw_data, offset, prefix_override = {}):
        """
        Generator: Parses raw_data (bytes) as ext4_xattr_entry structures and their referenced xattr values and yields
        tuples (xattr_name, xattr_value) where xattr_name (str) is the attribute name including its prefix and
        xattr_value (bytes) is the raw attribute value.
        raw_data must start with the first ext4_xattr_entry structure and offset specifies the offset to the "block start"
        for ext4_xattr_entry.e_value_offs.
        prefix_overrides allows specifying attributes apart from the default prefixes. The default prefix dictionary is
        updated with prefix_overrides.
        """
        prefixes = {
            0: "",
            1: "user.",
            2: "system.posix_acl_access",
            3: "system.posix_acl_default",
            4: "trusted.",
            6: "security.",
            7: "system.",
            8: "system.richacl"
        }
        prefixes.update(prefixes)

        # Iterator over ext4_xattr_entry structures
        i = 0
        while i < len(raw_data):
            xattr_entry = ext4_xattr_entry._from_buffer_copy(raw_data, i, platform64 = self.volume.platform64)

            if (xattr_entry.e_name_len | xattr_entry.e_name_index | xattr_entry.e_value_offs | xattr_entry.e_value_inum) == 0:
                # End of ext4_xattr_entry list
                break

            if not xattr_entry.e_name_index in prefixes:
                raise Ext4Error(f"Unknown attribute prefix {xattr_entry.e_name_index:d} in inode {self.inode_idx:d}")

            xattr_name = prefixes[xattr_entry.e_name_index] + xattr_entry.e_name.decode("iso-8859-2")

            if xattr_entry.e_value_inum != 0:
                # external xattr
                xattr_inode = self.volume.get_inode(xattr.e_value_inum)

                if not self.volume.ignore_flags and (xattr_inode.inode.i_flags & ext4_inode.EXT4_EA_INODE_FL) != 0:
                    raise Ext4Error(f"Inode {xattr_inode.inode_idx:d} associated with the extended attribute {xattr_name!r:s} of inode {self.inode_idx:d} is not marked as large extended attribute value.")

                # TODO Use xattr_entry.e_value_size or xattr_inode.inode.i_size?
                xattr_value = xattr_inode.open_read().read()
            else:
                # internal xattr
                xattr_value = raw_data[xattr_entry.e_value_offs + offset : xattr_entry.e_value_offs + offset + xattr_entry.e_value_size]

            yield (xattr_name, xattr_value)

            i += xattr_entry._size



    def directory_entry_comparator (dir_a, dir_b):
        """
        Sort-key for directory entries. It sortes entries in a way that directories come before anything else and within
        a group (directory / anything else) entries are sorted by their lower-case name. Entries whose lower-case names
        are equal are sorted by their actual names.
        """
        file_name_a, _, file_type_a = dir_a
        file_name_b, _, file_type_b = dir_b

        if file_type_a == InodeType.DIRECTORY == file_type_b or file_type_a != InodeType.DIRECTORY != file_type_b:
            tmp = wcscmp(file_name_a.lower(), file_name_b.lower())
            return tmp if tmp != 0 else wcscmp(file_name_a, file_name_b)
        else:
            return -1 if file_type_a == InodeType.DIRECTORY else 1

    directory_entry_key = functools.cmp_to_key(directory_entry_comparator)

    def get_inode (self, *relative_path, decode_name = None):
        """
        Returns the inode specified by the path relative_path (list of entry names) relative to this inode. "." and ".."
        usually are supported too, however in special cases (e.g. manually crafted volumes) they might not be supported
        due to them being real on-disk directory entries that might be missing or pointing somewhere else.
        decode_name is directly passed to open_dir.
        NOTE: Whitespaces will not be trimmed off the path's parts and "\\0" and "\\0\\0" as well as b"\\0" and b"\\0\\0" are
        seen as different names (unless decode_name actually trims the name).
        NOTE: Along the path file_type != FILETYPE_DIR will be ignored, however i_flags will not be ignored.
        """
        if not self.is_dir:
            raise Ext4Error(f"Inode {self.inode_idx:d} is not a directory.")

        current_inode = self

        for i, part in enumerate(relative_path):
            if not self.volume.ignore_flags and not current_inode.is_dir:
                current_path = "/".join(relative_path[:i])
                raise Ext4Error(f"{current_path!r:s} (Inode {inode_idx:d}) is not a directory.")

            file_name, inode_idx, file_type = next(filter(lambda entry: entry[0] == part, current_inode.open_dir(decode_name)), (None, None, None))

            if inode_idx == None:
                current_path = "/".join(relative_path[:i])
                raise FileNotFoundError(f"{part!r:s} not found in {current_path!r:s} (Inode {current_inode.inode_idx:d}).")

            current_inode = current_inode.volume.get_inode(inode_idx)


        return current_inode

    @property
    def is_dir (self):
        """
        Indicates whether the inode is marked as a directory.
        """
        return (self.inode.i_mode & ext4_inode.S_IFDIR) != 0

    @property
    def is_file (self):
        """
        Indicates whether the inode is marker as a regular file.
        """
        return (self.inode.i_mode & ext4_inode.S_IFREG) != 0

    @property
    def is_in_use (self):
        """
        Indicates whether the inode's associated bit in the inode bitmap is set.
        """
        group_idx, bitmap_bit = self.volume.get_inode_group(self.inode_idx)

        inode_usage_bitmap_offset = self.volume.group_descriptors[group_idx].bg_inode_bitmap * self.volume.block_size
        inode_usage_byte = self.volume.read(inode_usage_bitmap_offset + bitmap_bit // 8, 1)[0]

        return ((inode_usage_byte >> (7 - bitmap_bit % 8)) & 1) != 0

    @property
    def mode_str (self):
        """
        Returns the inode's permissions in form of a unix string (e.g. "-rwxrw-rw" or "drwxr-xr--").
        """
        special_flag = lambda letter, execute, special: {
            (False, False): "-",
            (False, True): letter.upper(),
            (True, False): "x",
            (True, True): letter.lower()
        }[(execute, special)]

        try:
            device_type = {
                ext4_inode.S_IFIFO  : "p",
                ext4_inode.S_IFCHR  : "c",
                ext4_inode.S_IFDIR  : "d",
                ext4_inode.S_IFBLK  : "b",
                ext4_inode.S_IFREG  : "-",
                ext4_inode.S_IFLNK  : "l",
                ext4_inode.S_IFSOCK : "s",
            }[self.inode.i_mode & 0xF000]
        except KeyError:
            device_type = "?"

        return "".join([
            device_type,

            "r" if (self.inode.i_mode & ext4_inode.S_IRUSR) != 0 else "-",
            "w" if (self.inode.i_mode & ext4_inode.S_IWUSR) != 0 else "-",
            special_flag("s", (self.inode.i_mode & ext4_inode.S_IXUSR) != 0, (self.inode.i_mode & ext4_inode.S_ISUID) != 0),

            "r" if (self.inode.i_mode & ext4_inode.S_IRGRP) != 0 else "-",
            "w" if (self.inode.i_mode & ext4_inode.S_IWGRP) != 0 else "-",
            special_flag("s", (self.inode.i_mode & ext4_inode.S_IXGRP) != 0, (self.inode.i_mode & ext4_inode.S_ISGID) != 0),

            "r" if (self.inode.i_mode & ext4_inode.S_IROTH) != 0 else "-",
            "w" if (self.inode.i_mode & ext4_inode.S_IWOTH) != 0 else "-",
            special_flag("t", (self.inode.i_mode & ext4_inode.S_IXOTH) != 0, (self.inode.i_mode & ext4_inode.S_ISVTX) != 0),
        ])

    def open_dir (self, decode_name = None):
        """
        Generator: Yields the directory entries as tuples (decode_name(name), inode, file_type) in their on-disk order,
        where name is the raw on-disk directory entry name (bytes). file_type is one of the Inode.IT_* constants. For
        special cases (e.g. invalid utf8 characters in entry names) you can try a different decoder (e.g.
        decode_name = lambda raw: raw).
        Default of decode_name = lambda raw: raw.decode("utf8")
        """
        # Parse args
        if decode_name == None:
            decode_name = lambda raw: raw.decode("utf8")

        if not self.volume.ignore_flags and not self.is_dir:
            raise Ext4Error(f"Inode ({self.inode_idx:d}) is not a directory.")

        # Hash trees are compatible with linear arrays
        #if (self.inode.i_flags & ext4_inode.EXT4_INDEX_FL) != 0:
        #    raise NotImplementedError("Hash trees are not implemented yet.")

        # Read raw directory content
        raw_data = self.open_read().read()
        offset = 0

        while offset < len(raw_data):
            dirent = ext4_dir_entry_2._from_buffer_copy(raw_data, offset, platform64 = self.volume.platform64)

            if dirent.file_type != InodeType.CHECKSUM:
                yield (decode_name(dirent.name), dirent.inode, dirent.file_type)

            offset += dirent.rec_len

    def open_read (self):
        """
        Returns an BlockReader instance for reading this inode's raw content.
        """
        if (self.inode.i_flags & ext4_inode.EXT4_EXTENTS_FL) != 0:
            # Obtain mapping from extents
            mapping = [] # List of MappingEntry instances

            nodes = queue.Queue()
            nodes.put_nowait(self.offset + ext4_inode.i_block.offset)

            while nodes.qsize() != 0:
                header_offset = nodes.get_nowait()
                header = self.volume.read_struct(ext4_extent_header, header_offset)

                if not self.volume.ignore_magic and header.eh_magic != 0xF30A:
                    raise MagicError(f"Invalid magic value in extent header at offset 0x{header_offset:X} of inode {self.inode_idx:d}: 0x{header.eh_magic:04X} (expected 0xF30A)")

                if header.eh_depth != 0:
                    indices = self.volume.read_struct(ext4_extent_idx * header.eh_entries, header_offset + ctypes.sizeof(ext4_extent_header))
                    for idx in indices: nodes.put_nowait(idx.ei_leaf * self.volume.block_size)
                else:
                    extents = self.volume.read_struct(ext4_extent * header.eh_entries, header_offset + ctypes.sizeof(ext4_extent_header))
                    for extent in extents:
                        mapping.append(MappingEntry(extent.ee_block, extent.ee_start, extent.ee_len))

            MappingEntry.optimize(mapping)
            return BlockReader(self.volume, len(self), mapping)
        else:
            # Inode uses inline data
            i_block = self.volume.read(self.offset + ext4_inode.i_block.offset, ext4_inode.i_block.size)
            return io.BytesIO(i_block[:self.inode.i_size])

    @property
    def size_readable (self):
        """
        Returns the inode's content length in a readable format (e.g. "123 bytes", "2.03 KiB" or "3.00 GiB"). Possible
        units are bytes, KiB, MiB, GiB, TiB, PiB, EiB, ZiB, YiB.
        """
        if self.inode.i_size < 1024:
            return f"{self.inode.i_size} bytes" if self.inode.i_size != 1 else "1 byte"
        else:
            units = ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
            unit_idx = min(int(math.log(self.inode.i_size, 1024)), len(units))

            return f"{self.inode.i_size / (1024 ** unit_idx):.2f} {units[unit_idx - 1]:s}"

    def xattrs (self, check_inline = True, check_block = True, force_inline = False, prefix_override = {}):
        """
        Generator: Yields the inode's extended attributes as tuples (name, value) in their on-disk order, where name (str)
        is the on-disk attribute name including its resolved name prefix and value (bytes) is the raw attribute value.
        check_inline and check_block control where to read attributes (the inode's inline data and/or the external data block
        pointed to by i_file_acl) and if check_inline as well as force_inline are set to True, the inode's inline data
        will not be verified to contain actual extended attributes and instead is just interpreted as such. prefix_overrides
        is directly passed to Inode._parse_xattrs.
        """
        # Inline xattrs
        inline_data_offset = self.offset + ext4_inode.EXT2_GOOD_OLD_INODE_SIZE + self.inode.i_extra_isize
        inline_data_length = self.offset + self.volume.superblock.s_inode_size - inline_data_offset

        if check_inline and inline_data_length > ctypes.sizeof(ext4_xattr_ibody_header):
            inline_data = self.volume.read(inline_data_offset, inline_data_length)
            xattrs_header = ext4_xattr_ibody_header.from_buffer_copy(inline_data)

            # TODO Find way to detect inline xattrs without checking the h_magic field to enable error detection with the h_magic field.
            if force_inline or xattrs_header.h_magic == 0xEA020000:
                offset = 4 * ((ctypes.sizeof(ext4_xattr_ibody_header) + 3) // 4) # The ext4_xattr_entry following the header is aligned on a 4-byte boundary
                for xattr_name, xattr_value in self._parse_xattrs(inline_data[offset:], 0, prefix_override = prefix_override):
                    yield (xattr_name, xattr_value)

        # xattr block(s)
        if check_block and self.inode.i_file_acl != 0:
            xattrs_block_start = self.inode.i_file_acl * self.volume.block_size
            xattrs_block = self.volume.read(xattrs_block_start, self.volume.block_size)

            xattrs_header = ext4_xattr_header.from_buffer_copy(xattrs_block)
            if not self.volume.ignore_magic and xattrs_header.h_magic != 0xEA020000:
                raise MagicError(f"Invalid magic value in xattrs block header at offset 0x{xattrs_block_start:X} of inode {self.inode_idx:d}: 0x{xattrs_header.h_magic} (expected 0xEA020000)")

            if xattrs_header.h_blocks != 1:
                raise Ext4Error(f"Invalid number of xattr blocks at offset 0x{xattrs_block_start:X} of inode {self.inode_idx:d}: {xattrs_header.h_blocks:d} (expected 1)")

            offset = 4 * ((ctypes.sizeof(ext4_xattr_header) + 3) // 4) # The ext4_xattr_entry following the header is aligned on a 4-byte boundary
            for xattr_name, xattr_value in self._parse_xattrs(xattrs_block[offset:], -offset, prefix_override = prefix_override):
                yield (xattr_name, xattr_value)



class BlockReader:
    """
    Maps disk blocks into a linear byte stream.
    NOTE: This class does not implement buffering or caching.
    """

    # OSError
    EINVAL = 22

    def __init__ (self, volume, byte_size, block_map):
        """
        Initializes a new block reader on the specified volume. mapping must be a list of MappingEntry instances. If
        you prefer a way to use 2-tuples (disk_block_idx, block_count) with inferred file_block_index entries, see
        MappingEntry.create_mapping.
        """
        self.byte_size = byte_size
        self.volume = volume

        self.cursor = 0

        block_map = list(map(MappingEntry.copy, block_map))

        # Optimize mapping (stich together)
        MappingEntry.optimize(block_map)
        self.block_map = block_map

    def __repr__ (self):
        return f"{type(self).__name__:s}(byte_size = {self.byte_size!r:s}, block_map = {self.block_map!r:s}, volume_uuid = {self.volume.uuid!r:s})"

    def get_block_mapping (self, file_block_idx):
        """
        Returns the disk block index of the file block specified by file_block_idx.
        """
        disk_block_idx = None

        # Find disk block
        for entry in self.block_map:
            if entry.file_block_idx <= file_block_idx < entry.file_block_idx + entry.block_count:
                block_diff = file_block_idx - entry.file_block_idx
                disk_block_idx = entry.disk_block_idx + block_diff
                break

        return disk_block_idx

    def read (self, byte_len = -1):
        """
        Reades up to byte_len bytes from the block device beginning at the cursor's current position. This operation will
        not exceed the inode's size. If -1 is passed for byte_len, the inode is read to the end.
        """
        # Parse args
        if byte_len < -1: raise ValueError("byte_len must be non-negative or -1")

        bytes_remaining = self.byte_size - self.cursor
        byte_len = bytes_remaining if byte_len == -1 else max(0, min(byte_len, bytes_remaining))

        if byte_len == 0: return b""

        # Reading blocks
        start_block_idx = self.cursor // self.volume.block_size
        end_block_idx = (self.cursor + byte_len - 1) // self.volume.block_size
        end_of_stream_check = byte_len

        blocks = [self.read_block(i) for i in range(start_block_idx, end_block_idx - start_block_idx + 1)]

        start_offset = self.cursor % self.volume.block_size
        if start_offset != 0: blocks[0] = blocks[0][start_offset:]
        byte_len = (byte_len + start_offset - self.volume.block_size - 1) % self.volume.block_size + 1
        blocks[-1] = blocks[-1][:byte_len]

        result = b"".join(blocks)

        # Check read
        if len(result) != end_of_stream_check:
            raise EndOfStreamError(f"The volume's underlying stream ended {byte_len - len(result):d} bytes before EOF.")

        self.cursor += len(result)
        return result

    def read_block (self, file_block_idx):
        """
        Reads one block from disk (return a zero-block if the file block is not mapped)
        """
        disk_block_idx = self.get_block_mapping(file_block_idx)

        if disk_block_idx != None:
            return self.volume.read(disk_block_idx * self.volume.block_size, self.volume.block_size)
        else:
            return bytes([0] * self.volume.block_size)

    def seek (self, seek, seek_mode = io.SEEK_SET):
        """
        Moves the internal cursor along the file (not the disk) and behaves like BufferedReader.seek
        """
        if seek_mode == io.SEEK_CUR:
            seek += self.cursor
        elif seek_mode == io.SEEK_END:
            seek += self.byte_size
        # elif seek_mode == io.SEEK_SET:
        #     seek += 0

        if seek < 0:
            raise OSError(BlockReader.EINVAL, "Invalid argument") # Exception behavior copied from IOBase.seek

        self.cursor = seek
        return seek

    def tell (self):
        """
        Returns the internal cursor's current file offset.
        """
        return self.cursor



class Tools:
    """
    Provides helpful utility functions
    """

    def list_dir (
        volume,
        identifier,
        decode_name = None,
        sort_key = Inode.directory_entry_key,
        line_format = None,
        file_types = {0 : "unkn", 1 : "file", 2 : "dir", 3 : "chr", 4 : "blk", 5 : "fifo", 6 : "sock", 7 : "sym"}
    ):
        """
        Similar to "ls -la" this function lists all entries from a directory of volume.

        identifier might be an Inode instance, an integer describing the directory's inode index, a str/bytes describing
        the directory's full path or a list of entry names. decode_name is directly passed to open_dir. See Inode.get_inode
        for more details.

        sort_key is the key-function used for sorting the directories entries. If None is passed, the call to sorted is
        omitted.

        line_format is a format string specifying each line's format or a function formatting each line. It is used as
        follows:

            line_format(
                file_name = file_name, # Entry name
                inode = volume.get_inode(inode_idx), # Referenced inode
                file_type = file_type, # Entry type (int)
                file_type_str = file_types[file_type] if file_type in file_types else "?" # Entry type (str, see next paragraph)
            )

        The default of line_format is the following function:

            def line_format (file_name, inode, file_type, file_type_str):
                if file_type == InodeType.SYMBOLIC_LINK:
                    link_target = inode.open_read().read().decode("utf8")
                    return f"{inode.mode_str:s}  {inode.size_readable: >10s}  {file_name:s}  ->  {link_target:s}"
                else:
                    return f"{inode.mode_str:s}  {inode.size_readable: >10s}  {file_name:s}"

        file_types is a dictionary specifying the names of the different entry types.
        """
        # Parse arguments
        if isinstance(identifier, Inode):
            inode = identifier
        elif isinstance(identifier, int):
            inode = volume.get_inode(identifier)
        elif isinstance(identifier, str):
            identifier = identifier.strip(" /").split("/")

            if len(identifier) == 1 and identifier[0] == "":
                inode = volume.root
            else:
                inode = volume.root.get_inode(*identifier)
        elif isinstance(identifier, list):
            inode = volume.root.get_inode(*identifier)

        if line_format == None:
            def _line_format (file_name, inode, file_type, file_type_str):
                if file_type == InodeType.SYMBOLIC_LINK:
                    link_target = inode.open_read().read().decode("utf8")
                    return f"{inode.mode_str:s}  {inode.size_readable: >10s}  {file_name:s}  ->  {link_target:s}"
                else:
                    return f"{inode.mode_str:s}  {inode.size_readable: >10s}  {file_name:s}"

            line_format = _line_format
        elif isinstance(line_format, str):
            line_format = line_format.format

        # Print directory
        entries = inode.open_dir(decode_name) if sort_key is None else sorted(inode.open_dir(decode_name), key = sort_key)

        for file_name, inode_idx, file_type in entries:
            print(line_format(
                file_name = file_name,
                inode = volume.get_inode(inode_idx),
                file_type = file_type,
                file_type_str = file_types[file_type] if file_type in file_types else "?"
            ))