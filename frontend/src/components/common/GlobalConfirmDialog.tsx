import ConfirmDialog from './ConfirmDialog';
import { useConfirmStore } from '../../hooks/useConfirm';

const GlobalConfirmDialog = () => {
  const { isOpen, title, message, confirmText, cancelText, variant, showCancel, close } =
    useConfirmStore();

  return (
    <ConfirmDialog
      isOpen={isOpen}
      title={title}
      message={message}
      confirmText={confirmText}
      cancelText={cancelText}
      variant={variant}
      showCancel={showCancel}
      onConfirm={() => close(true)}
      onCancel={() => close(false)}
    />
  );
};

export default GlobalConfirmDialog;
