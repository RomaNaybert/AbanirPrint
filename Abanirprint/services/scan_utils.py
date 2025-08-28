# services/scan_utils.py

import os
from PIL import Image
from aiogram.types import FSInputFile
import pythoncom
import win32com.client

device_manager = win32com.client.Dispatch("WIA.DeviceManager")
devices = device_manager.DeviceInfos
print(f"Найдено устройств: {devices.Count}")

for i in range(devices.Count):
    print(f"[{i}] {devices[i].Properties['Name'].Value}")

def scan_document(output_path: str):
    pythoncom.CoInitialize()  # для потоков

    try:
        device_manager = win32com.client.Dispatch("WIA.DeviceManager")
        scanner = None
        for i in range(device_manager.DeviceInfos.Count):
            name = device_manager.DeviceInfos[i].Properties["Name"].Value
            if "HP DJ 2300" in name:
                scanner = device_manager.DeviceInfos[i].Connect()
                break

        if scanner is None:
            raise Exception("Сканер 'HP DJ 2300' не найден.")

        item = scanner.Items[0]
        img = item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}")  # Это ImageFormatJPEG

        stream = win32com.client.Dispatch("ADODB.Stream")
        stream.Type = 1  # binary
        stream.Open()
        stream.Write(img.FileData.BinaryData)
        stream.SaveToFile(output_path, 2)
        stream.Close()

        print(f"[scan_document] Скан успешно сохранён: {output_path}")

    except Exception as e:
        print(f"[scan_document] Ошибка сканирования: {e}")
        raise e


def merge_scans_to_pdf(image_paths: list[str], output_pdf_path: str):
    images = [Image.open(p).convert("RGB") for p in image_paths]
    if images:
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
    print(f"[merge_scans_to_pdf] PDF сохранён в {output_pdf_path}")

def print_file(file_path: str):
    from services.print_manager import print_and_wait
    print_and_wait(file_path, copies=1)