import asyncio
import os

import pytest

from typing import (
    Optional,
)

from click.testing import CliRunner

from eth2deposit import deposit
from eth2deposit.deposit import main
from eth2deposit.utils.constants import DEFAULT_VALIDATOR_KEYS_FOLDER_NAME
from eth2deposit.key_handling.keystore import Keystore


def clean_key_folder(my_folder_path: str) -> None:
    validator_keys_folder_path = os.path.join(my_folder_path, DEFAULT_VALIDATOR_KEYS_FOLDER_NAME)
    if not os.path.exists(validator_keys_folder_path):
        return

    _, _, key_files = next(os.walk(validator_keys_folder_path))
    for key_file_name in key_files:
        os.remove(os.path.join(validator_keys_folder_path, key_file_name))
    os.rmdir(validator_keys_folder_path)
    os.rmdir(my_folder_path)


def test_deposit(monkeypatch) -> None:
    # monkeypatch get_mnemonic
    def get_mnemonic(language: str, words_path: str, entropy: Optional[bytes]=None) -> str:
        return "fakephrase"

    monkeypatch.setattr(deposit, "get_mnemonic", get_mnemonic)

    # Prepare folder
    my_folder_path = os.path.join(os.getcwd(), 'TESTING_TEMP_FOLDER')
    clean_key_folder(my_folder_path)
    if not os.path.exists(my_folder_path):
        os.mkdir(my_folder_path)

    runner = CliRunner()
    inputs = ['5', 'english', 'MyPassword', 'MyPassword', 'fakephrase']
    data = '\n'.join(inputs)
    result = runner.invoke(main, ['--folder', my_folder_path], input=data)

    assert result.exit_code == 0

    # Check files
    validator_keys_folder_path = os.path.join(my_folder_path, DEFAULT_VALIDATOR_KEYS_FOLDER_NAME)
    _, _, key_files = next(os.walk(validator_keys_folder_path))

    def get_uuid(key_file: str) -> str:
        keystore = Keystore.from_json(key_file)
        return keystore.uuid

    all_uuid = [
        get_uuid(validator_keys_folder_path + '/' + key_file)
        for key_file in key_files
        if key_file.startswith('keystore')
    ]
    assert len(set(all_uuid)) == 5

    # Clean up
    clean_key_folder(my_folder_path)


@pytest.mark.asyncio
async def test_script() -> None:
    my_folder_path = os.path.join(os.getcwd(), 'TESTING_TEMP_FOLDER')
    if not os.path.exists(my_folder_path):
        os.mkdir(my_folder_path)

    if os.name == 'nt':  # Windows
        run_script_cmd = 'sh deposit.sh'
    else:  # Mac or Linux
        run_script_cmd = './deposit.sh'

    install_cmd = run_script_cmd + ' install'
    proc = await asyncio.create_subprocess_shell(
        install_cmd,
    )
    await proc.wait()

    cmd_args = [
        run_script_cmd,
        '--num_validators', '1',
        '--mnemonic_language', 'english',
        '--password', 'MyPassword',
        '--folder', my_folder_path,
    ]
    proc = await asyncio.create_subprocess_shell(
        ' '.join(cmd_args),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    seed_phrase = ''
    parsing = False
    async for out in proc.stdout:
        output = out.decode('utf-8').rstrip()
        if output.startswith("This is your seed phrase."):
            parsing = True
        elif output.startswith("Please type your mnemonic"):
            parsing = False
        elif parsing:
            seed_phrase += output
            if len(seed_phrase) > 0:
                encoded_phrase = seed_phrase.encode()
                proc.stdin.write(encoded_phrase)
                proc.stdin.write(b'\n')

    assert len(seed_phrase) > 0

    # Check files
    validator_keys_folder_path = os.path.join(my_folder_path, DEFAULT_VALIDATOR_KEYS_FOLDER_NAME)
    _, _, key_files = next(os.walk(validator_keys_folder_path))

    # Clean up
    clean_key_folder(my_folder_path)
