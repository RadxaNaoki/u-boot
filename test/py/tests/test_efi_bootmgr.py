# SPDX-License-Identifier:      GPL-2.0+
""" Unit test for UEFI bootmanager
"""

import shutil
import pytest
from subprocess import call, check_call, CalledProcessError
from tests import fs_helper

@pytest.mark.boardspec('sandbox')
@pytest.mark.buildconfigspec('cmd_efidebug')
@pytest.mark.buildconfigspec('cmd_bootefi_bootmgr')
@pytest.mark.singlethread
def test_efi_bootmgr(u_boot_console):
    """ Unit test for UEFI bootmanager
    The efidebug command is used to set up UEFI load options.
    The bootefi bootmgr loads initrddump.efi as a payload.
    The crc32 of the loaded initrd.img is checked

    Args:
        u_boot_console -- U-Boot console
    """
    try:
        scratch_dir = u_boot_console.config.persistent_data_dir + '/scratch'

        check_call('mkdir -p %s' % scratch_dir, shell=True)

        with open(scratch_dir + '/initrd-1.img', 'w', encoding = 'ascii') as file:
            file.write("initrd 1")

        with open(scratch_dir + '/initrd-2.img', 'w', encoding = 'ascii') as file:
            file.write("initrd 2")

        shutil.copyfile(u_boot_console.config.build_dir + '/lib/efi_loader/initrddump.efi',
                        scratch_dir + '/initrddump.efi')

        efi_bootmgr_data = fs_helper.mk_fs(u_boot_console.config, 'vfat',
                                           0x100000, 'test_efi_bootmgr',
                                           scratch_dir)
        check_call(f'qemu-img create {efi_bootmgr_data}.real 2M', shell=True)
        check_call(f'echo "label: dos" | sfdisk {efi_bootmgr_data}.real', shell=True)
        check_call(f'echo "1k,1M,c" | sfdisk {efi_bootmgr_data}.real', shell=True)
        check_call(f'dd if={efi_bootmgr_data} of={efi_bootmgr_data}.real bs=1k seek=1', shell=True)
        shutil.move(efi_bootmgr_data + '.real', efi_bootmgr_data)
        u_boot_console.run_command(cmd = f'host bind 0 {efi_bootmgr_data}')

        u_boot_console.run_command(cmd = 'efidebug boot add ' \
            '-b 0001 label-1 host 0:1 initrddump.efi ' \
            '-i host 0:1 initrd-1.img -s nocolor')
        u_boot_console.run_command(cmd = 'efidebug boot dump')
        u_boot_console.run_command(cmd = 'efidebug boot order 0001')
        u_boot_console.run_command(cmd = 'bootefi bootmgr')
        response = u_boot_console.run_command(cmd = 'load', wait_for_echo=False)
        assert 'crc32: 0x181464af' in response
        u_boot_console.run_command(cmd = 'exit', wait_for_echo=False)

        u_boot_console.run_command(cmd = 'efidebug boot add ' \
            '-B 0002 label-2 host 0:1 initrddump.efi ' \
            '-I host 0:1 initrd-2.img -s nocolor')
        u_boot_console.run_command(cmd = 'efidebug boot dump')
        u_boot_console.run_command(cmd = 'efidebug boot order 0002')
        u_boot_console.run_command(cmd = 'bootefi bootmgr')
        response = u_boot_console.run_command(cmd = 'load', wait_for_echo=False)
        assert 'crc32: 0x811d3515' in response
        u_boot_console.run_command(cmd = 'exit', wait_for_echo=False)

        u_boot_console.run_command(cmd = 'efidebug boot rm 0001')
        u_boot_console.run_command(cmd = 'efidebug boot rm 0002')
    except CalledProcessError as err:
        pytest.skip('Preparing test_efi_bootmgr image failed')
        call('rm -f %s' % efi_bootmgr_data, shell=True)
        return
    finally:
        call('rm -rf %s' % scratch_dir, shell=True)
        call('rm -f %s' % efi_bootmgr_data, shell=True)
